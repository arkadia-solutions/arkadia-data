"""
What to improve in AK-DATA: a closer look at one AI benchmark report.

    python -m arkadia.bench.analyze reports/ai-bundled-<model>.json [--vs json] [--format akcd]
    make analyze                      (the newest reports/ai-*.json)

The headline accuracy says little on its own. This prints:

1. accuracy per format with its 95% interval;
2. a paired comparison with a reference format (default JSON): the same
   question answered right in one format and wrong in the other. Only these
   questions tell the formats apart; the p-value (exact McNemar test) says
   whether the difference is more than chance — below 0.05 it is real;
3. accuracy per question type and per dataset next to the reference, so a
   weak spot (e.g. counting long lists, irregular records) stands out;
4. every question the reference answered and the chosen format did not, with
   the expected and the given answer — the material for the next change to
   the format, the encoder or the format definition.

A change is an improvement when, on a new run, the paired comparison moves in
its favour with p < 0.05, or the weak question type closes the gap.
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from .ai_bench import wilson
from .colors import C

Key = Tuple[str, int, str]  # dataset, repeat, question text


def outcomes(report: Dict[str, Any]) -> Dict[str, Dict[Key, bool]]:
    """format -> {(dataset, repeat, question): answered right}."""
    kinds = {
        (ds, q["text"]): q["kind"]
        for ds, qs in report.get("questions", {}).items()
        for q in qs
    }
    out: Dict[str, Dict[Key, bool]] = defaultdict(dict)
    for t in report.get("trials", []):
        if t.get("error"):
            continue
        missed = {m["q"] for m in t.get("misses", [])}
        for q in report["questions"].get(t["dataset"], []):
            out[t["format"]][(t["dataset"], t.get("repeat", 0), q["text"])] = (
                q["text"] not in missed
            )
    out["_kinds"] = kinds  # type: ignore[assignment]
    return out


def mcnemar(b: int, c: int) -> float:
    """Exact two-sided McNemar p-value for b vs c discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


def _pct(v: float) -> str:
    return f"{v * 100:5.1f}%"


def analyze(report: Dict[str, Any], vs: str, fmt: str, limit: int = 40) -> str:
    res = outcomes(report)
    kinds = res.pop("_kinds")  # type: ignore[arg-type]
    labels = report.get("formats", {})
    keys = [k for k in labels if k in res]
    if vs not in res:
        raise ValueError(
            f"reference format '{vs}' not in the report ({', '.join(keys)})"
        )
    lines: List[str] = []
    who = f"{report.get('provider')} · {report.get('model')}"
    n_q = sum(len(v) for v in report.get("questions", {}).values())
    lines.append(
        f"{C.BOLD}AK-DATA ANALYSIS{C.RESET}  {C.DIM}{who} · {n_q} questions · {report.get('source')}{C.RESET}\n"
    )

    lines.append(f"{C.BOLD}1. Accuracy{C.RESET}")
    for k in keys:
        vals = list(res[k].values())
        c, n = sum(vals), len(vals)
        lo, hi = wilson(c, n)
        lines.append(
            f"   {labels[k]:28}{_pct(c / n)}   95% {lo * 100:4.1f}–{hi * 100:4.1f}%   ({c}/{n})"
        )

    lines.append(
        f"\n{C.BOLD}2. Paired with {labels[vs]}{C.RESET} {C.DIM}(same question: only one of the two right){C.RESET}"
    )
    for k in keys:
        if k == vs:
            continue
        common = res[k].keys() & res[vs].keys()
        b = sum(1 for q in common if res[k][q] and not res[vs][q])
        c = sum(1 for q in common if res[vs][q] and not res[k][q])
        p = mcnemar(b, c)
        verdict = (
            f"{C.GREEN}better{C.RESET}"
            if p < 0.05 and b > c
            else f"{C.RED}worse{C.RESET}"
            if p < 0.05
            else f"{C.DIM}no real difference{C.RESET}"
        )
        lines.append(
            f"   {labels[k]:28}+{b:<3} only here   −{c:<3} only in {labels[vs]:16} p={p:.3f}  {verdict}"
        )

    def table(title: str, group) -> None:
        lines.append(f"\n{C.BOLD}{title}{C.RESET}")
        groups = sorted({group(q) for q in res[vs]})
        head = (
            "   " + f"{'':18}{'n':>5}" + "".join(f"{labels[k][:14]:>16}" for k in keys)
        )
        lines.append(f"{C.DIM}{head}{C.RESET}")
        for g in groups:
            row = f"   {g[:18]:18}"
            n = sum(1 for q in res[vs] if group(q) == g)
            row += f"{n:>5}"
            ref = sum(v for q, v in res[vs].items() if group(q) == g) / max(1, n)
            for k in keys:
                vals = [v for q, v in res[k].items() if group(q) == g]
                acc = sum(vals) / max(1, len(vals))
                col = C.RED if acc < ref - 0.1 else C.GREEN if acc > ref + 0.1 else ""
                row += f"{col}{acc * 100:>15.0f}%{C.RESET}"
            lines.append(row)

    table("3. Per question type", lambda q: kinds.get((q[0], q[2]), "?"))
    table("   Per dataset", lambda q: q[0])

    lines.append(
        f"\n{C.BOLD}4. Right in {labels[vs]}, wrong in {labels.get(fmt, fmt)}{C.RESET} "
        f"{C.DIM}— start here{C.RESET}"
    )
    got = {
        (t["dataset"], t.get("repeat", 0), m["q"]): m
        for t in report.get("trials", [])
        if t["format"] == fmt
        for m in t.get("misses", [])
    }
    shown = 0
    for q, ok in sorted(res.get(fmt, {}).items()):
        if not ok and res[vs].get(q):
            m = got.get(q, {})
            lines.append(
                f"   {C.DIM}[{q[0]} · {kinds.get((q[0], q[2]), '?')}]{C.RESET} {q[2]}\n"
                f"      expected {json.dumps(m.get('expected'), ensure_ascii=False)[:80]}   got {str(m.get('got'))[:80]!r}"
            )
            shown += 1
            if shown >= limit:
                lines.append(f"   {C.DIM}… (--limit to show more){C.RESET}")
                break
    if not shown:
        lines.append("   none")
    return "\n".join(lines) + "\n"


def newest(folder: pathlib.Path) -> pathlib.Path:
    files = [p for p in folder.glob("ai-*.json") if "dry-run" not in p.name]
    if not files:
        raise FileNotFoundError(
            f"No ai-*.json with model results in {folder} — run make benchmark NETWORK=1 MODEL=… first"
        )
    return max(files, key=lambda p: p.stat().st_mtime)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m arkadia.bench.analyze", description=__doc__.split("\n\n")[0]
    )
    p.add_argument(
        "report", nargs="?", help="reports/ai-*.json (default: the newest in reports/)"
    )
    p.add_argument("--vs", default="json", help="reference format (default json)")
    p.add_argument(
        "--format", default="akcd", help="format whose misses are listed (default akcd)"
    )
    p.add_argument("--limit", type=int, default=40, help="misses to list")
    args = p.parse_args(argv)
    try:
        path = (
            pathlib.Path(args.report)
            if args.report
            else newest(pathlib.Path("../reports"))
        )
        report = json.loads(path.read_text(encoding="utf-8"))
        print(analyze(report, args.vs, args.format, args.limit))
    except (FileNotFoundError, ValueError) as exc:
        print(f"{C.RED}Error:{C.RESET} {exc}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
