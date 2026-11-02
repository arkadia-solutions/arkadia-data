"""
Every test of an AI benchmark run, for checking it by hand.

`export_run(report, folder)` writes one run (one model) as small JSON files
that the website loads on demand:

    <folder>/<run>/index.json         the run, every dataset and question with
                                      the expected answer and, per format,
                                      the given answer and whether it was right
    <folder>/<run>/<dataset>.json     per format: the exact user prompt, the
                                      model's raw reply and the parsed answers

Reports written before prompts and replies were recorded (they only kept the
wrong answers) are exported too: the prompts are rebuilt from the datasets,
the seed and the stored questions, and kept only when their token count is
exactly the one measured during the run; replies are marked as not recorded.

    python -m arkadia.bench.runs reports/ai-bundled-gpt-5.json [...] [-o benchmarks/runs]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Any, Dict, List, Optional

from .ai_bench import SYSTEM, Question, _prompt, _use_hint, benchmark_sets
from .formats import available_formats


def run_slug(report: Dict[str, Any]) -> str:
    text = f"{report.get('provider', '')}-{report.get('model', '')}".lower()
    return re.sub(r"[^a-z0-9.]+", "-", text).strip("-") or "run"


# The format hint as earlier versions sent it (before the sentence about
# shorter records and $size), so older runs are rebuilt exactly.
LEGACY_HINTS = [
    "Data is in AK-Data format: <field:type,...> is a header; (v1,v2) is a "
    "record whose values follow the header order; {key:value} is a named "
    "record; [..] is a list; <[...]> describes every record in the list; "
    "<type> before a value overrides its type.",
]


def _rebuild_prompts(report: Dict[str, Any]) -> Dict[tuple, tuple]:
    """
    (dataset, format) -> (user prompt, exact) for reports without prompts.
    exact: the token count equals the one measured in the run (tried with the
    current and the earlier format hints); otherwise the closest rebuild.
    """
    source = report.get("source") or ""
    if not source.startswith("bundled datasets"):
        return {}
    try:
        from arkadia.data.tokens import get_tokenizer

        tok = get_tokenizer(report.get("tokenizer") or "o200k_base")
        sets = {
            d.name: d
            for d in benchmark_sets(
                None, int(report.get("generated") or 0), int(report.get("seed") or 7)
            )
        }
    except Exception:
        return {}
    formats = available_formats(variants=True)
    system = tok.count(report.get("system") or SYSTEM)
    out = {}
    for t in report.get("trials", []):
        if "format" not in t or "dataset" not in t:
            continue
        key = (t["dataset"], t["format"])
        if key in out or t["dataset"] not in sets or t["format"] not in formats:
            continue
        qs = [Question(**q) for q in report["questions"].get(t["dataset"], [])]
        user, _, hint = _prompt(
            formats[t["format"]],
            sets[t["dataset"]].data,
            qs,
            _use_hint(report.get("hint") or "auto", t["format"]),
        )
        candidates = [user] + (
            [user.replace(hint, old, 1) for old in LEGACY_HINTS] if hint else []
        )
        want = t.get("prompt_tokens")
        best = min(candidates, key=lambda u: abs(system + tok.count(u) - (want or 0)))
        out[key] = (best, system + tok.count(best) == want)
    return out


# ---------------------------------------------------------------------------
# The answer by code: a JavaScript (and TypeScript) expression per question
# ---------------------------------------------------------------------------

_P = r"`([^`]+)`"
_V = r"(.+?)"


def _acc(path: str) -> str:
    """`rows` / `a.b` / `(root)` as a JavaScript accessor on `data`."""
    if path == "(root)":
        return "data"
    return "data" + "".join(f"[{json.dumps(p)}]" for p in path.split("."))


def _prop(name: str) -> str:
    return f"[{json.dumps(name)}]"


def question_code(text: str) -> Optional[str]:
    """
    The JavaScript expression that computes a question's answer from `data`
    (the dataset as JSON). Valid TypeScript too. None for unknown questions.
    """
    rules = [
        (rf"^How many items are in {_P}\?$", lambda p: f"{_acc(p)}.length"),
        (rf"^How many entries does {_P} have\?$", lambda p: f"{_acc(p)}.length"),
        (
            rf"^Which fields does each item in {_P} have\? List the field names\.$",
            lambda p: f"Object.keys({_acc(p)}[0])",
        ),
        (
            rf"^In {_P}, how many entries does {_P} have for the item whose {_P} is {_V}\?$",
            lambda p, f, k, v: (
                f"{_acc(p)}.find((r) => r{_prop(k)} === {v}){''.join(_prop(x) for x in f.split('.'))}.length"
            ),
        ),
        (
            rf"^In {_P}, what is the sum of {_P} over the {_P} of the item whose {_P} is {_V}\?$",
            lambda p, f, lst, k, v: (
                f"{_acc(p)}.find((r) => r{_prop(k)} === {v}){_prop(lst)}.reduce((sum, x) => sum + x{_prop(f)}, 0)"
            ),
        ),
        (
            rf"^In {_P}, what is the sum of {_P} over the items whose {_P} is {_V}\?$",
            lambda p, f, c, v: (
                f"{_acc(p)}.filter((r) => r{_prop(c)} === {v}).reduce((sum, r) => sum + r{_prop(f)}, 0)"
            ),
        ),
        (
            rf"^In {_P}, what is {_P} of the last item\?$",
            lambda p, f: f"{_acc(p)}[{_acc(p)}.length - 1]{_prop(f)}",
        ),
        (
            rf"^In {_P}, what is {_P} of the (\d+)(?:st|nd|rd|th) item \(counting from 1\)\?$",
            lambda p, f, n: f"{_acc(p)}[{int(n) - 1}]{_prop(f)}",
        ),
        (
            rf"^In {_P}, what is {_P} of the item whose {_P} is {_V}\?$",
            lambda p, f, k, v: (
                f"{_acc(p)}.find((r) => r{_prop(k)} === {v}){''.join(_prop(x) for x in f.split('.'))}"
            ),
        ),
        (
            rf"^How many items in {_P} have {_P} equal to {_V} and {_P} equal to {_V}\?$",
            lambda p, f1, v1, f2, v2: (
                f"{_acc(p)}.filter((r) => r{_prop(f1)} === {v1} && r{_prop(f2)} === {v2}).length"
            ),
        ),
        (
            rf"^How many items in {_P} have {_P} equal to {_V}\?$",
            lambda p, f, v: f"{_acc(p)}.filter((r) => r{_prop(f)} === {v}).length",
        ),
        (
            rf"^How many items in {_P} have a {_P} field at all \(items without it do not count\)\?$",
            lambda p, f: f"{_acc(p)}.filter((r) => {json.dumps(f)} in r).length",
        ),
        (
            rf"^How many items in {_P} have {_V} in {_P}\?$",
            lambda p, v, f: (
                f"{_acc(p)}.filter((r) => r{_prop(f)}.includes({v})).length"
            ),
        ),
        (
            rf"^In {_P}, which item has the (highest|lowest) {_P}\? Answer with its {_P}\.$",
            lambda p, w, f, k: (
                f"{_acc(p)}.reduce((best, r) => (r{_prop(f)} {'>' if w == 'highest' else '<'} best{_prop(f)} ? r : best)){_prop(k)}"
            ),
        ),
        (
            rf"^In {_P}, list the {_P} of every item whose {_P} is greater than {_V}\.$",
            lambda p, k, f, v: (
                f"{_acc(p)}.filter((r) => r{_prop(f)} > {v}).map((r) => r{_prop(k)})"
            ),
        ),
        (rf"^What is the value of {_P}\?$", lambda p: _acc(p)),
    ]
    for pattern, make in rules:
        m = re.match(pattern, text)
        if m:
            return make(*m.groups())
    return None


def _datasets_of(report: Dict[str, Any]) -> Dict[str, Any]:
    """The data of each dataset of a run (bundled + generated), when known."""
    source = report.get("source") or ""
    if not source.startswith("bundled datasets"):
        return {}
    try:
        return {
            d.name: d.data
            for d in benchmark_sets(
                None, int(report.get("generated") or 0), int(report.get("seed") or 7)
            )
        }
    except Exception:
        return {}


def build(report: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    """(index, {dataset: details}) of one AI report."""
    labels = report.get("formats", {})
    recorded = any(t.get("reply") is not None for t in report.get("trials", []))
    rebuilt = {} if recorded else _rebuild_prompts(report)
    data_of = _datasets_of(report)
    descriptions = {}
    datasets: List[Dict[str, Any]] = []
    details: Dict[str, Dict[str, Any]] = {}
    by_ds: Dict[str, List[Dict[str, Any]]] = {}
    for t in report.get("trials", []):
        if t.get("repeat", 0) == 0 and "format" in t and "dataset" in t:
            by_ds.setdefault(t["dataset"], []).append(t)
    for name, qs in report.get("questions", {}).items():
        trials = {t["format"]: t for t in by_ds.get(name, [])}
        results: Dict[str, List[Dict[str, Any]]] = {}
        tokens: Dict[str, int] = {}
        errors: Dict[str, str] = {}
        detail: Dict[str, Any] = {}
        for fmt in labels:
            t = trials.get(fmt)
            if t is None:
                continue
            tokens[fmt] = t.get("prompt_tokens")
            if t.get("error"):
                errors[fmt] = t["error"]
            misses = {m["q"]: m for m in t.get("misses", [])}
            rows = []
            for i, q in enumerate(qs):
                if t.get("ok"):
                    ok = bool(t["ok"][i]) if i < len(t["ok"]) else False
                    got = t["answers"][i] if i < len(t.get("answers", [])) else None
                else:
                    text = q.get("text")
                    ok = text not in misses and not t.get("error")
                    got = misses[text].get("got") if text in misses else None
                rows.append({"ok": ok, "got": got})
            results[fmt] = rows
            exact = True
            prompt = t.get("prompt")
            if not prompt and (name, fmt) in rebuilt:
                prompt, exact = rebuilt[(name, fmt)]
            detail[fmt] = {
                "prompt": prompt or None,
                # False: rebuilt with the current code, not byte-exact
                "prompt_exact": exact,
                "reply": t.get("reply"),
                "prompt_tokens": t.get("prompt_tokens"),
                "api_input_tokens": t.get("api_input_tokens"),
                "api_output_tokens": t.get("api_output_tokens"),
                "seconds": round(t.get("seconds") or 0, 2),
                "error": t.get("error"),
            }
        datasets.append(
            {
                "name": name,
                "description": descriptions.get(name, ""),
                "questions": [
                    {
                        "code": question_code(q.get("text") or ""),
                        "text": q.get("text"),
                        "kind": q.get("kind"),
                        "expected": q.get("answer"),
                    }
                    for q in qs
                ],
                "results": results,
                "tokens": tokens,
                "errors": errors,
            }
        )
        if name in data_of:
            # the dataset itself, so the answers can be checked by code
            detail["__data"] = data_of[name]
        details[name] = detail
    index = {
        "run": run_slug(report),
        "provider": report.get("provider"),
        "model": report.get("model"),
        "source": report.get("source"),
        "hint": report.get("hint"),
        "seed": report.get("seed"),
        "generated": report.get("generated"),
        "repeats": report.get("repeats", 1),
        "reasoning": report.get("reasoning"),
        "tokenizer": report.get("tokenizer"),
        "system": report.get("system") or SYSTEM,
        "formats": labels,
        "recorded": recorded,
        "prompts": "recorded" if recorded else ("rebuilt" if rebuilt else "missing"),
        "summary": report.get("summary", {}),
        "datasets": datasets,
    }
    return index, details


def export_run(
    report: Dict[str, Any], folder: pathlib.Path, date: Optional[str] = None
) -> str:
    """Writes the run's files under folder/<run>/; returns the run slug."""
    index, details = build(report)
    if date:
        index["date"] = date
    out = pathlib.Path(folder) / index["run"]
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.json"):
        old.unlink()
    (out / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    for name, detail in details.items():
        (out / f"{name}.json").write_text(
            json.dumps(detail, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    return index["run"]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m arkadia.bench.runs",
        description="Export AI benchmark reports test by test for the website.",
    )
    p.add_argument("reports", nargs="+", help="reports/ai-*.json")
    p.add_argument("-o", "--out", default="../benchmarks/runs", help="output folder")
    p.add_argument(
        "--site",
        default=None,
        help="only the models listed in this website file (benchmarks/benchmark.json)",
    )
    args = p.parse_args(argv)
    shown = None
    if args.site and pathlib.Path(args.site).exists():
        site = json.loads(pathlib.Path(args.site).read_text(encoding="utf-8"))
        shown = {
            (m.get("provider"), m.get("model"))
            for m in site.get("ai", {}).get("models", [])
        }
    for path in args.reports:
        report = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        if report.get("dry_run"):
            print(f"skip {path} (dry run)")
            continue
        if (
            shown is not None
            and (report.get("provider"), report.get("model")) not in shown
        ):
            print(f"skip {path} (not on the website)")
            continue
        index, _ = build(report)
        slug = export_run(report, pathlib.Path(args.out))
        print(f"{path} → {args.out}/{slug}/  (prompts {index['prompts']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
