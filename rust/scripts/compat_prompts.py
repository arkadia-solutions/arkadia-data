"""
Checks that `ak-data prompt --example N` (Rust) writes exactly the prompts of
examples/prompts/*/prompts.json (Python) — every example, format and metadata
combination.

    python rust/scripts/compat_prompts.py rust/target/release/ak-data
"""

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
FLAGS = {"json": "json", "toon": "toon", "akd": "ak-data", "akcd": "ak-data-compact"}
COMBOS = {"none": [], "comments": ["--comments"], "attributes": ["--attributes"], "both": ["--comments", "--attributes"]}


def main() -> int:
    binary = sys.argv[1]
    bad = total = 0
    for f in sorted((ROOT / "examples" / "prompts").glob("*/prompts.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for fmt, by_combo in d["prompts"].items():
            for combo, expected in by_combo.items():
                args = [binary, "prompt", "--no-color", "--example", str(d["id"]), "-f", FLAGS[fmt], *COMBOS[combo]]
                got = subprocess.run(args, capture_output=True, text=True).stdout
                total += 1
                if got.rstrip("\n") != expected.rstrip("\n"):
                    bad += 1
                    if bad <= 3:
                        print(f"DIFF example {d['id']} {fmt} {combo}")
                        for i, (a, b) in enumerate(zip(got.splitlines(), expected.splitlines())):
                            if a != b:
                                print(f"  line {i}: rust   {a[:120]!r}\n          python {b[:120]!r}")
                                break
    print(f"{total} prompts · {bad} difference(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
