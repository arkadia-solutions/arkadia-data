"""
Cross-language check: the Rust `ak-data` binary must write exactly what the
Python package writes (AK-DATA compact and laid out, TOON) and decode it back
to the original JSON.

    python rust/scripts/compat.py rust/target/release/ak-data [--random 300]

Run from the repository root with the Python package importable
(`cd python && uv run --all-extras python ../rust/scripts/compat.py …`).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import shlex
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python" / "src"))

import arkadia.data as akd  # noqa: E402
from arkadia.data import layout  # noqa: E402

try:
    import toon_format
except ImportError:  # TOON is checked only when the reference is installed
    toon_format = None


def corpus(n_random: int):
    from arkadia.bench.datasets import bundled

    for ds in bundled():
        yield f"dataset:{ds.name}", ds.data
    for p in sorted((ROOT / "python" / "src" / "arkadia" / "bench" / "examples").glob("*.json")):
        ex = json.loads(p.read_text(encoding="utf-8"))
        yield f"example:{p.stem}", ex["data"]
        yield f"expected:{p.stem}", {ex["answer"]["name"]: ex["expected"]}
    for p in sorted((ROOT / "python" / "data").rglob("*.json")):
        try:
            yield f"fixture:{p.relative_to(ROOT)}", json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
    edge = [
        None, True, 0, -1.5, 1e-7, 12345678901234, "", "a\"b\\c\nd\te", "żółw 🐢",
        [], {}, [[]], [{}], {"": 1}, {"": 1, "0": 2}, {"a b": [1, "x", None]},
        [1, "2", None, 3.5, True], [{"a": 1}, {"b": 2}], [{"a": 1}, {"a": "x"}, {"a": None}],
        {"x": [{"id": 1, "t": [1, 2]}, {"id": 2, "t": ["a"]}]}, [[1, 2], ["a"], []],
        {"n": {"m": {"k": [{"v": 1}]}}}, [{"a": {"b": 1}}, {"a": {"c": 2}}, {"a": 3}],
        {"true": "false", "null": "null", "1": "-1"}, ["-", "#x", " lead", "trail ", "1e5", "05"],
    ]
    for i, v in enumerate(edge):
        yield f"edge:{i}", v
    rnd = random.Random(7)
    for i in range(n_random):
        yield f"random:{i}", rand_value(rnd, 0)


KEYS = ["id", "name", "a", "b", "", "x y", "0", "type", "ünï", "`q`", "k.v"]
STRS = ["", "x", "Ada", "a,b", "a:b", 'q"t', "back\\s", "line\nbreak", "tab\t", "null", "123", " s", "-x", "🙂"]


def rand_value(r: random.Random, depth: int):
    roll = r.random()
    if depth > 3 or roll < 0.35:
        return r.choice([None, True, False, r.randint(-1000, 1000), round(r.uniform(-1e4, 1e4), r.randint(0, 4)), r.choice(STRS)])
    if roll < 0.6:
        n = r.randint(0, 5)
        return {r.choice(KEYS) + (str(j) if r.random() < 0.3 else ""): rand_value(r, depth + 1) for j in range(n)}
    if roll < 0.8:
        keys = r.sample(KEYS, r.randint(1, 4))
        return [
            {k: rand_value(r, depth + 2) for k in (keys if r.random() < 0.8 else r.sample(KEYS, 2))}
            for _ in range(r.randint(0, 6))
        ]
    return [rand_value(r, depth + 1) for _ in range(r.randint(0, 6))]


def run(binary: str, args: list[str], stdin: str) -> str:
    # Bytes, not text mode: text mode would turn "\r" into "\n".
    p = subprocess.run([*shlex.split(binary), *args], input=stdin.encode("utf-8"), capture_output=True)
    out, err = p.stdout.decode("utf-8"), p.stderr.decode("utf-8", "replace")
    if p.returncode != 0:
        raise RuntimeError(f"{' '.join(args)}: {err.strip()}")
    return out[:-1] if out.endswith("\n") else out


def has_float(v) -> bool:
    if isinstance(v, float):
        return True
    if isinstance(v, list):
        return any(map(has_float, v))
    if isinstance(v, dict):
        return any(map(has_float, v.values()))
    return False


def huge_int(v) -> bool:
    """Integers beyond 64 bits become floats in serde_json (same value, other spelling)."""
    if isinstance(v, bool):
        return False
    if isinstance(v, int):
        return not (-(2**63) <= v < 2**64)
    if isinstance(v, list):
        return any(map(huge_int, v))
    if isinstance(v, dict):
        return any(map(huge_int, v.values()))
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("binary")
    ap.add_argument("--random", type=int, default=300)
    ap.add_argument("--no-toon", action="store_true", help="skip the TOON comparison")
    ap.add_argument("--floats-as-js", action="store_true", help="JavaScript numbers: 199.0 is written 199")
    a = ap.parse_args()
    failures = []
    py_crashes = []
    total = 0
    for name, data in corpus(a.random):
        if huge_int(data):
            continue
        total += 1
        src = json.dumps(data, ensure_ascii=False)
        checks = [
            ("compact", ["read", "-c"], akd.dumps(data)),
            ("pretty", ["read"], layout.pretty(akd.dumps(data))),
        ]
        if a.floats_as_js and has_float(data):
            continue
        if toon_format is not None and not a.no_toon:
            checks.append(("toon", ["read", "-t", "toon"], toon_format.encode(data, indent_size=2, delimiter=",")))
        for label, args, expected in checks:
            try:
                got = run(a.binary, args, src)
            except RuntimeError as exc:
                failures.append((name, label, str(exc), expected))
                continue
            if got != expected:
                i = next((k for k, (x, y) in enumerate(zip(got, expected)) if x != y), min(len(got), len(expected)))
                failures.append((name, label, got[max(0, i - 60):], expected[max(0, i - 60):]))
        # Rust reads its own output back to the original…
        try:
            own = run(a.binary, ["read", "-c"], src)
            back = json.loads(run(a.binary, ["read", "-t", "json-min", "--strict"], own))
            if back != data:
                failures.append((name, "round-trip", json.dumps(back)[:200], src[:200]))
        except (RuntimeError, json.JSONDecodeError) as exc:
            failures.append((name, "round-trip", str(exc), src[:200]))
        # …and reads Python's text exactly as Python does.
        py_text = akd.dumps(data, indent=2)
        try:
            reference = akd.loads(py_text, strict=False)
        except Exception as exc:  # a crash in the Python decoder, reported apart
            py_crashes.append((name, repr(exc)))
            continue
        try:
            back = json.loads(run(a.binary, ["read", "-t", "json-min"], py_text))
            if back != reference:
                failures.append((name, "decode", json.dumps(back)[:200], src[:200]))
        except (RuntimeError, json.JSONDecodeError) as exc:
            failures.append((name, "decode", str(exc), src[:200]))
    for name, label, got, expected in failures[:15]:
        print(f"✗ {name} [{label}]\n   rust:   {got[:300]!r}\n   python: {expected[:300]!r}")
    for name, exc in py_crashes[:5]:
        print(f"! python decoder crashed on {name}: {exc}")
    print(f"{total} values · {len(failures)} difference(s) · {len(py_crashes)} Python decoder crash(es)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
