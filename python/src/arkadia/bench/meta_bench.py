"""
Metadata benchmark: does a model understand data better with comments and
tags, and what do they cost?

The annotated datasets (`arkadia.bench.annotated`) are sent in six variants —
JSON, JSON with notes, AK-DATA without metadata, with /* comments */, with
$attributes/#tags, and with both — together with two kinds of questions:

    meta    answerable only with the metadata (a status code's meaning, a
            unit, which records are tests …)
    plain   answerable from the data alone (lookups, counts)

Without metadata the "meta" questions are expected to fail; the benchmark
shows how much the metadata helps, whether comments or attributes work
better, whether it disturbs the plain questions, and the token price.

    from arkadia.bench.meta_bench import run
    report = run(provider)          # provider=None: dry run, prompt sizes only
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

from arkadia.data.prompt import FORMAT_DEFINITION
from arkadia.data.tokens import get_tokenizer

from .ai_bench import SYSTEM, Provider, parse_answers, score
from .annotated import VARIANT_LABELS, VARIANTS, Annotated, datasets, variants


@dataclass
class MetaTrial:
    dataset: str
    variant: str
    prompt_tokens: int
    data_tokens: int
    meta_correct: int = 0
    meta_total: int = 0
    plain_correct: int = 0
    plain_total: int = 0
    misses: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class MetaReport:
    kind: str
    provider: str
    model: str
    tokenizer: str
    dry_run: bool
    variants: Dict[str, str]
    results: List[MetaTrial] = field(default_factory=list)
    questions: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    def table(self) -> Dict[str, Dict[str, Any]]:
        """Per variant: tokens and accuracy on meta / plain questions."""
        out: Dict[str, Dict[str, Any]] = {}
        for v in self.variants:
            ts = [t for t in self.results if t.variant == v and t.error is None]
            if not ts:
                continue
            mt, mc = sum(t.meta_total for t in ts), sum(t.meta_correct for t in ts)
            pt, pc = sum(t.plain_total for t in ts), sum(t.plain_correct for t in ts)
            out[v] = {
                "label": self.variants[v],
                "prompt_tokens": sum(t.prompt_tokens for t in ts),
                "data_tokens": sum(t.data_tokens for t in ts),
                "meta_accuracy": None if self.dry_run or not mt else mc / mt,
                "plain_accuracy": None if self.dry_run or not pt else pc / pt,
                "meta_questions": mt,
                "plain_questions": pt,
            }
        return out

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["table"] = self.table()
        return d


def prompt(ds: Annotated, variant: str) -> tuple[str, str]:
    """(user prompt, data text) for a dataset in a variant."""
    data = variants(ds)[variant]
    parts = []
    if variant not in ("json", "json-notes"):
        parts.append(FORMAT_DEFINITION)
    parts.append(f"<data>\n{data}\n</data>")
    parts.append(
        "Questions:\n"
        + "\n".join(f"{i}. {q.text}" for i, q in enumerate(ds.questions, 1))
    )
    return "\n\n".join(parts), data


def list_prompts() -> List[Dict[str, Any]]:
    out = []
    for ds in datasets():
        for v in VARIANTS:
            user, _ = prompt(ds, v)
            out.append(
                {
                    "dataset": ds.name,
                    "format": v,
                    "kind": "metadata",
                    "system": SYSTEM,
                    "user": user,
                    "answers": [q.answer for q in ds.questions],
                }
            )
    return out


def run(
    provider: Optional[Provider],
    encoding: str = "o200k_base",
    parallel: int = 4,
    progress: Optional[Callable[[str], None]] = None,
) -> MetaReport:
    tok = get_tokenizer(encoding)
    report = MetaReport(
        kind="metadata",
        provider=provider.name if provider else "dry-run",
        model=provider.model if provider else "",
        tokenizer=tok.label,
        dry_run=provider is None,
        variants={v: VARIANT_LABELS[v] for v in VARIANTS},
    )
    jobs = []
    for ds in datasets():
        report.questions[ds.name] = [asdict(q) for q in ds.questions]
        jobs += [(ds, v) for v in VARIANTS]

    def ask(job):
        ds, v = job
        user, data = prompt(ds, v)
        t = MetaTrial(ds.name, v, tok.count(SYSTEM) + tok.count(user), tok.count(data))
        t.meta_total = sum(q.needs_meta for q in ds.questions)
        t.plain_total = len(ds.questions) - t.meta_total
        if provider is None:
            return t
        try:
            reply = provider.complete(
                SYSTEM, user, max_tokens=60 + 40 * len(ds.questions)
            )
        except Exception as exc:  # noqa: BLE001 — reported per trial
            t.error = str(exc)
            return t
        for q, a in zip(ds.questions, parse_answers(reply.text, len(ds.questions))):
            ok = score(a, q.answer)
            if q.needs_meta:
                t.meta_correct += ok
            else:
                t.plain_correct += ok
            if not ok:
                t.misses.append(
                    {"q": q.text, "expected": q.answer, "got": a, "meta": q.needs_meta}
                )
        if progress:
            progress(
                f"{ds.name:10} {v:11} meta {t.meta_correct}/{t.meta_total} plain {t.plain_correct}/{t.plain_total}"
            )
        return t

    with ThreadPoolExecutor(max_workers=max(1, parallel if provider else 1)) as pool:
        report.results = list(pool.map(ask, jobs))
    return report


def to_markdown(report: MetaReport) -> str:
    who = (
        "dry run (no model)"
        if report.dry_run
        else f"{report.provider} · `{report.model}`"
    )
    rows = report.table()
    lines = [
        f"# ak-data metadata benchmark — {who}",
        "",
        "Same data in six variants. *meta* questions need the metadata (codes, units, tags);",
        f"*plain* questions need only the data. Tokens counted with {report.tokenizer}.",
        "",
        "| variant | prompt tokens | data tokens | meta questions | plain questions |",
        "|---|---:|---:|---:|---:|",
    ]
    pct = lambda v: "–" if v is None else f"{v * 100:.0f}%"  # noqa: E731
    for v, r in rows.items():
        lines.append(
            f"| {r['label']} | {r['prompt_tokens']:,} | {r['data_tokens']:,} | "
            f"{pct(r['meta_accuracy'])} | {pct(r['plain_accuracy'])} |"
        )
    return "\n".join(lines) + "\n"
