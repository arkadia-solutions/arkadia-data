"""
Benchmark numbers for the website (`make benchmark` on the bundled datasets).

`export()` reads the token and AI reports of one run and writes one small JSON
file — `benchmarks/benchmark.json` in the repository and, when the landing
page is next to it, `arkadia-landing/src/data/benchmark.json` — that the page
renders at build time. Results of real models are kept across runs (keyed by
provider and model), so a later run without a model only refreshes the token
numbers and prompt sizes.
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib
from typing import Any, Dict, Iterable, List, Optional

from .runs import export_run, run_slug

SCHEMA = 1
HEADLINE_TOKENIZER = "o200k_base"


def _tokens(report: Dict[str, Any]) -> Dict[str, Any]:
    keys = list(report["formats"])
    datasets = []
    for row in report["rows"]:
        cells = row["cells"]
        datasets.append(
            {
                "name": row["dataset"],
                "description": row.get("description") or "",
                "tokens": {
                    k: cells[k]["tokens"] for k in keys if not cells[k].get("error")
                },
                "chars": {
                    k: cells[k]["chars"] for k in keys if not cells[k].get("error")
                },
                "lossless": {k: cells[k].get("lossless") for k in keys},
                "encode_ms": {
                    k: round(cells[k].get("encode_ms") or 0, 4) for k in keys
                },
                "decode_ms": {
                    k: round(cells[k]["decode_ms"], 4)
                    for k in keys
                    if cells[k].get("decode_ms") is not None
                },
            }
        )
    return {
        "exact": bool(report.get("exact_tokens")),
        "formats": [{"key": k, "label": report["formats"][k]} for k in keys],
        "datasets": datasets,
        "totals": report.get("totals", {}),
        "savings_vs_json_pct": {
            k: round(v, 2) for k, v in report.get("savings_vs_json_pct", {}).items()
        },
        "wins": report.get("wins", {}),
    }


def _headline(tokens: Dict[str, Any]) -> Dict[str, Any]:
    totals = tokens["totals"]
    out: Dict[str, Any] = {"tokenizer": HEADLINE_TOKENIZER}
    if "akcd" in totals:
        for rival in ("json", "json-min", "yaml", "toon"):
            if totals.get(rival):
                out[f"akcd_vs_{rival.replace('-', '_')}_pct"] = round(
                    (totals["akcd"] - totals[rival]) / totals[rival] * 100, 1
                )
    out["lossless"] = all(
        v in (True, None) for d in tokens["datasets"] for v in d["lossless"].values()
    )
    out["datasets"] = len(tokens["datasets"])
    return out


def _ai(report: Dict[str, Any]) -> Dict[str, Any]:
    summary = report.get("summary", {})
    keys = [k for k in report["formats"] if k in summary]
    formats = []
    for k in keys:
        s = summary[k]
        formats.append(
            {
                "key": k,
                "label": report["formats"][k],
                "accuracy": s.get("accuracy"),
                "ci95": s.get("ci95"),
                "correct": s.get("correct"),
                "questions": s.get("questions"),
                "prompt_tokens": s.get("prompt_tokens"),
                "data_tokens": s.get("data_tokens"),
                "correct_per_10k_tokens": s.get("correct_per_10k_tokens"),
                "write_valid": s.get("write_valid"),
            }
        )
    kinds = sorted({kind for k in keys for kind in summary[k].get("by_kind", {})})
    by_kind = {
        kind: {k: summary[k]["by_kind"].get(kind) for k in keys} for kind in kinds
    }
    return {
        "provider": report.get("provider"),
        "model": report.get("model"),
        "dry_run": bool(report.get("dry_run")),
        "tokenizer": report.get("tokenizer"),
        "hint": report.get("hint"),
        "datasets": len({t["dataset"] for t in report.get("trials", [])}),
        "questions": sum(len(v) for v in report.get("questions", {}).values()),
        "source": report.get("source"),
        "repeats": report.get("repeats", 1),
        "reasoning": report.get("reasoning"),
        "formats": formats,
        "by_kind": by_kind,
        "run": run_slug(report),
        "by_kind_n": {
            kind: max(summary[k].get("by_kind_n", {}).get(kind, 0) for k in keys)
            for kind in kinds
        },
    }


def _meta(report: Dict[str, Any]) -> Dict[str, Any]:
    table = report.get("table", {})
    return {
        "provider": report.get("provider"),
        "model": report.get("model"),
        "dry_run": bool(report.get("dry_run")),
        "tokenizer": report.get("tokenizer"),
        "datasets": len(report.get("questions", {})),
        "questions": sum(len(v) for v in report.get("questions", {}).values()),
        "meta_questions": sum(
            sum(1 for q in v if q.get("needs_meta"))
            for v in report.get("questions", {}).values()
        ),
        "variants": [dict(key=k, **v) for k, v in table.items()],
    }


def _merge_meta(
    previous: Optional[Dict[str, Any]], reports: Iterable[Dict[str, Any]], now: str
) -> Dict[str, Any]:
    old = (previous or {}).get("ai", {}).get("meta") or {}
    sizes = old.get("prompt_sizes")
    models = {f"{m.get('provider')}/{m.get('model')}": m for m in old.get("models", [])}
    for r in reports:
        m = _meta(r)
        sizes = {
            k: m[k] for k in ("tokenizer", "datasets", "questions", "meta_questions")
        } | {
            "variants": [
                {k: v[k] for k in ("key", "label", "prompt_tokens", "data_tokens")}
                for v in m["variants"]
            ]
        }
        if not m["dry_run"]:
            m["date"] = now
            models[f"{m['provider']}/{m['model']}"] = m
    return {
        "prompt_sizes": sizes,
        "models": sorted(models.values(), key=lambda m: m.get("date") or ""),
    }


def build(
    token_reports: Iterable[Dict[str, Any]],
    ai_reports: Iterable[Dict[str, Any]],
    previous: Optional[Dict[str, Any]] = None,
    version: str = "",
    meta_reports: Iterable[Dict[str, Any]] = (),
) -> Dict[str, Any]:
    """The website JSON from the reports of one run (and the previous file)."""
    token_reports = list(token_reports)
    tokens = {r["tokenizer"]: _tokens(r) for r in token_reports}
    if not tokens:
        raise ValueError("no token benchmark report to export")
    head_key = (
        HEADLINE_TOKENIZER if HEADLINE_TOKENIZER in tokens else next(iter(tokens))
    )
    now = _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()

    models: Dict[str, Dict[str, Any]] = {}
    for m in (previous or {}).get("ai", {}).get("models", []):
        models[f"{m.get('provider')}/{m.get('model')}"] = m
    prompt_sizes = (previous or {}).get("ai", {}).get("prompt_sizes")
    for report in ai_reports:
        ai = _ai(report)
        prompt_sizes = {
            "tokenizer": ai["tokenizer"],
            "datasets": ai["datasets"],
            "questions": ai["questions"],
            "source": ai["source"],
            "hint": ai["hint"],
            "formats": [
                {k: f[k] for k in ("key", "label", "prompt_tokens", "data_tokens")}
                for f in ai["formats"]
            ],
        }
        if not ai["dry_run"]:
            ai["date"] = now
            models[f"{ai['provider']}/{ai['model']}"] = ai

    return {
        "schema": SCHEMA,
        "generated": now,
        "version": version,
        "source": token_reports[0].get("source", "bundled datasets"),
        "headline": dict(_headline(tokens[head_key]), tokenizer=head_key),
        "tokens": tokens,
        "ai": {
            "prompt_sizes": prompt_sizes,
            "models": sorted(models.values(), key=lambda m: m.get("date") or ""),
            "meta": _merge_meta(previous, meta_reports, now),
        },
    }


def export(
    token_paths: List[pathlib.Path],
    ai_paths: List[pathlib.Path],
    targets: List[pathlib.Path],
    version: str = "",
    meta_paths: Optional[List[pathlib.Path]] = None,
) -> List[pathlib.Path]:
    """Writes the website JSON to every target; returns the written paths."""
    token_reports = [json.loads(p.read_text(encoding="utf-8")) for p in token_paths]
    ai_reports = [json.loads(p.read_text(encoding="utf-8")) for p in ai_paths]
    meta_reports = [
        json.loads(p.read_text(encoding="utf-8")) for p in (meta_paths or [])
    ]
    previous = None
    for t in targets:
        if t.exists():
            try:
                previous = json.loads(t.read_text(encoding="utf-8"))
                break
            except ValueError:
                continue
    data = build(token_reports, ai_reports, previous, version, meta_reports)
    # Every test of each model run, next to the first target (runs/<run>/).
    if targets:
        for report in ai_reports:
            if not report.get("dry_run"):
                try:
                    export_run(report, targets[0].parent / "runs", data["generated"])
                except Exception as exc:  # the website numbers matter more
                    print(f"Run details not exported: {exc}")
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    written = []
    for t in targets:
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text(text, encoding="utf-8")
        written.append(t)
    return written
