"""
Token / speed / fidelity benchmark: JSON vs YAML vs TOON vs AK-Data.

    from arkadia.bench.bench import run
    report = run()                 # bundled datasets
    report = run(directory="data") # every *.json in a folder
"""

from __future__ import annotations

import statistics
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from arkadia.data.tokens import DEFAULT_ENCODING, get_tokenizer

from .datasets import Dataset, resolve
from .formats import Format, available_formats


@dataclass
class Cell:
    tokens: int
    chars: int
    encode_ms: float
    decode_ms: Optional[float]
    lossless: Optional[bool]
    error: Optional[str] = None


@dataclass
class Row:
    dataset: str
    description: str
    cells: Dict[str, Cell]
    reference_ok: Optional[bool] = None


@dataclass
class Report:
    tokenizer: str
    exact_tokens: bool
    source: str
    formats: Dict[str, str]
    rows: List[Row] = field(default_factory=list)

    def totals(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for key in self.formats:
            values = [
                r.cells[key].tokens
                for r in self.rows
                if key in r.cells and r.cells[key].error is None
            ]
            if len(values) == len(self.rows):
                out[key] = sum(values)
        return out

    def savings(self, baseline: str = "json") -> Dict[str, float]:
        totals = self.totals()
        base = totals.get(baseline)
        if not base:
            return {}
        return {k: (v - base) / base * 100 for k, v in totals.items()}

    def wins(self) -> Dict[str, int]:
        """How many datasets each format encodes in the fewest tokens."""
        out = {k: 0 for k in self.formats}
        for r in self.rows:
            ok = {k: c.tokens for k, c in r.cells.items() if c.error is None}
            if ok:
                out[min(ok, key=ok.get)] += 1
        return out

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tokenizer": self.tokenizer,
            "exact_tokens": self.exact_tokens,
            "source": self.source,
            "formats": self.formats,
            "rows": [asdict(r) for r in self.rows],
            "totals": self.totals(),
            "savings_vs_json_pct": self.savings(),
            "wins": self.wins(),
        }


def _time(fn, repeats: int):
    result = fn()
    if repeats <= 0:
        return result, 0.0
    samples = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t0)
    return result, statistics.median(samples) * 1000


def _measure(fmt: Format, data: Any, count, repeats: int) -> Cell:
    try:
        text, enc_ms = _time(lambda: fmt.encode(data), repeats)
    except Exception as exc:  # a format that cannot represent the data
        return Cell(0, 0, 0.0, None, None, f"encode: {exc}")
    dec_ms = None
    lossless = None
    if fmt.decode is not None:
        try:
            back, dec_ms = _time(lambda: fmt.decode(text), repeats)
            lossless = back == data
        except Exception as exc:
            return Cell(count(text), len(text), enc_ms, None, False, f"decode: {exc}")
    return Cell(count(text), len(text), enc_ms, dec_ms, lossless)


def _check_reference(ds: Dataset) -> Optional[bool]:
    if ds.reference is None:
        return None
    import arkadia.data as akd

    result = akd.decode(ds.reference)
    return not result.errors


def run(
    directory: Optional[str] = None,
    formats: Optional[List[str]] = None,
    encoding: str = DEFAULT_ENCODING,
    repeats: int = 20,
    datasets: Optional[List[Dataset]] = None,
) -> Report:
    tok = get_tokenizer(encoding)
    all_formats = available_formats()
    keys = [k for k in (formats or list(all_formats)) if k in all_formats]
    unknown = [k for k in (formats or []) if k not in all_formats]
    if unknown:
        raise ValueError(f"Unknown or unavailable format(s): {', '.join(unknown)}")
    sets = datasets if datasets is not None else resolve(directory)
    report = Report(
        tokenizer=tok.name,
        exact_tokens=tok.exact,
        source=directory or "bundled datasets",
        formats={k: all_formats[k].label for k in keys},
    )
    for ds in sets:
        cells = {k: _measure(all_formats[k], ds.data, tok.count, repeats) for k in keys}
        report.rows.append(Row(ds.name, ds.description, cells, _check_reference(ds)))
    return report


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def to_markdown(report: Report) -> str:
    keys = list(report.formats)
    lines = [
        f"# AK-DATA benchmark ({report.source})",
        "",
        f"Tokenizer: `{report.tokenizer}`{'' if report.exact_tokens else ' (approximate counts)'}",
        "",
        "| dataset | " + " | ".join(report.formats[k] for k in keys) + " |",
        "|---|" + "---:|" * len(keys),
    ]
    for r in report.rows:
        best = min(
            (c.tokens for c in r.cells.values() if c.error is None), default=None
        )
        vals = []
        for k in keys:
            c = r.cells[k]
            if c.error:
                vals.append("error")
                continue
            v = f"{c.tokens:,}"
            if c.tokens == best:
                v = f"**{v}**"
            if c.lossless is False:
                v += " ⚠"
            vals.append(v)
        lines.append(f"| {r.dataset} | " + " | ".join(vals) + " |")
    totals = report.totals()
    savings = report.savings()
    lines.append(
        "| **total** | "
        + " | ".join(f"{totals[k]:,}" if k in totals else "–" for k in keys)
        + " |"
    )
    lines.append(
        "| vs JSON | "
        + " | ".join(f"{savings[k]:+.1f}%" if k in savings else "–" for k in keys)
        + " |"
    )
    lines += ["", "⚠ = decoding did not return the original data."]
    return "\n".join(lines) + "\n"
