"""
HTML report from the token and AI benchmark JSON results, with a written
summary. Built as the last step of `make benchmark` (python -m arkadia.bench).

The summary is written by a model when one is configured (same providers as
the AI benchmark), otherwise it is generated from the numbers; the report says
which. Everything is in one self-contained HTML file (inline CSS and SVG, no
scripts or external assets).
"""

from __future__ import annotations

import datetime as _dt
import html
import json
import pathlib
import platform
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

LABELS = {
    "json": "JSON",
    "json-min": "JSON min",
    "yaml": "YAML",
    "toon": "TOON",
    "akd": "AK-Data",
    "akcd": "AK-Data compact",
    "akd-n": "AK-Data + sizes",
    "akcd-n": "AK-Data compact + sizes",
}
COLORS = {
    "json": "#9b9a94",
    "json-min": "#6f6e69",
    "yaml": "#a78bda",
    "toon": "#e8762d",
    "akd": "#2f9e5b",
    "akcd": "#1f8a4c",
    "akd-n": "#3fb873",
    "akcd-n": "#13703a",
}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


@dataclass
class Inputs:
    benchmarks: List[Tuple[str, Dict[str, Any]]] = field(default_factory=list)
    ai: List[Tuple[str, Dict[str, Any]]] = field(default_factory=list)


def load_inputs(paths: List[pathlib.Path]) -> Inputs:
    """
    Reads report JSON files (or every *.json in the given folders) and sorts
    them into token benchmarks and AI benchmarks by their content.
    """
    files: List[pathlib.Path] = []
    for p in paths:
        p = pathlib.Path(p)
        if p.is_dir():
            files += sorted(p.glob("*.json"))
        elif p.exists():
            files.append(p)
    out = Inputs()
    files = sorted(set(files))
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        if "rows" in data and "totals" in data:
            out.benchmarks.append((f.stem, data))
        elif "trials" in data and "summary" in data:
            out.ai.append((f.stem, data))
    # bundled datasets with the default tokenizer first; measured AI runs first
    out.benchmarks.sort(
        key=lambda nb: (
            nb[1].get("source") != "bundled datasets",
            nb[1].get("tokenizer") != "o200k_base",
            nb[0],
        )
    )
    out.ai.sort(key=lambda na: (bool(na[1].get("dry_run")), na[0]))
    return out


# ---------------------------------------------------------------------------
# Facts (shared by the automatic summary and the model prompt)
# ---------------------------------------------------------------------------


def _short(source: Any) -> Any:
    """'/home/me/project/data' -> 'project/data' (keeps reports shareable)."""
    if isinstance(source, str) and "/" in source:
        return "/".join(pathlib.PurePath(source).parts[-2:])
    return source


def _pct(a: float, b: float) -> float:
    return (a - b) / b * 100 if b else 0.0


def facts(inputs: Inputs) -> Dict[str, Any]:
    """The numbers the summary talks about, in one small structure."""
    out: Dict[str, Any] = {"token_benchmarks": [], "ai_benchmarks": []}
    for name, b in inputs.benchmarks:
        totals = b.get("totals", {})
        rows = b.get("rows", [])
        wins = b.get("wins", {})
        lossy = sorted(
            {
                k
                for r in rows
                for k, c in r["cells"].items()
                if c.get("lossless") is False
            }
        )
        losses = []
        for r in rows:
            ok = {k: c["tokens"] for k, c in r["cells"].items() if not c.get("error")}
            if "akcd" in ok and ok:
                best = min(ok, key=ok.get)
                if best != "akcd" and best != "akd":
                    losses.append(
                        {
                            "dataset": r["dataset"],
                            "winner": best,
                            "gap_pct": round(_pct(ok["akcd"], ok[best]), 1),
                        }
                    )
        rivals = {k: v for k, v in totals.items() if k not in ("akcd", "akd")}
        best_rival = min(rivals, key=rivals.get) if rivals else None
        out["token_benchmarks"].append(
            {
                "name": name,
                "source": _short(b.get("source")),
                "tokenizer": b.get("tokenizer"),
                "exact_tokens": b.get("exact_tokens"),
                "datasets": len(rows),
                "totals": totals,
                "vs_json_pct": {
                    k: round(v, 1) for k, v in b.get("savings_vs_json_pct", {}).items()
                },
                "akcd_vs_best_rival_pct": round(
                    _pct(totals["akcd"], totals[best_rival]), 1
                )
                if best_rival and "akcd" in totals
                else None,
                "best_rival": best_rival,
                "wins": wins,
                "lossy_formats": lossy,
                "datasets_where_akdata_loses": losses,
            }
        )
    for name, a in inputs.ai:
        s = a.get("summary", {})
        out["ai_benchmarks"].append(
            {
                "name": name,
                "provider": a.get("provider"),
                "model": a.get("model"),
                "dry_run": a.get("dry_run"),
                "hint": a.get("hint"),
                "questions": sum(len(v) for v in a.get("questions", {}).values()),
                "formats": {
                    k: {
                        "accuracy_pct": None
                        if v.get("accuracy") is None
                        else round(v["accuracy"] * 100, 1),
                        "prompt_tokens": v.get("prompt_tokens"),
                        "correct_per_10k_tokens": None
                        if v.get("correct_per_10k_tokens") is None
                        else round(v["correct_per_10k_tokens"], 1),
                        "write_valid_pct": None
                        if v.get("write_valid") is None
                        else round(v["write_valid"] * 100),
                        "by_kind_pct": {
                            kk: round(vv * 100)
                            for kk, vv in v.get("by_kind", {}).items()
                        },
                    }
                    for k, v in s.items()
                },
                "errors": sum(1 for t in a.get("trials", []) if t.get("error")),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------

_T = {
    "en": {
        "tok": "On {n} datasets ({src}, {tokz}), AK-Data compact used {akcd} tokens: "
        "{vs_json:.1f}% fewer than JSON and {vs_rival:.1f}% {dir} than the best "
        "alternative, {rival}.",
        "wins": "It had the fewest tokens on {w} of {n} datasets.",
        "loses": "It lost on: {items}.",
        "lossy": "Formats that did not decode back to the original: {items}.",
        "lossless": "Every format decoded back to the original data.",
        "ai": "{model}: accuracy {items}.",
        "ai_cmp": "AK-Data compact answered {acc_diff:+.1f} points vs JSON with "
        "{tok_diff:.1f}% fewer prompt tokens ({eff:.1f} vs {eff_json:.1f} correct "
        "answers per 10k tokens).",
        "ai_write": "Writing: AK-Data output decoded correctly in {w}% of attempts "
        "(JSON {wj}%).",
        "dry": "AI benchmark ran dry (no model): prompt sizes only — JSON {j} vs "
        "AK-Data {a} tokens. Accuracy is not measured yet.",
        "none_ai": "No AI benchmark results yet; run `make benchmark MODEL=...` "
        "to measure comprehension.",
        "rec_go": "Recommendation: use AK-Data compact for data the model reads; "
        "its accuracy is not more than 2 points below JSON.",
        "rec_wait": "Recommendation: check the wrong answers before switching — "
        "accuracy is more than 2 points below JSON.",
        "fewer": "fewer",
        "more": "more",
    },
    "pl": {
        "tok": "Na {n} zestawach danych ({src}, {tokz}) AK-Data compact zużył "
        "{akcd} tokenów: o {vs_json:.1f}% mniej niż JSON i o {vs_rival:.1f}% "
        "{dir} niż najlepsza alternatywa, {rival}.",
        "wins": "Najmniej tokenów miał w {w} z {n} zestawów.",
        "loses": "Przegrał w: {items}.",
        "lossy": "Formaty, które nie wróciły do oryginału: {items}.",
        "lossless": "Każdy format zdekodował się do oryginalnych danych.",
        "ai": "{model}: trafność {items}.",
        "ai_cmp": "AK-Data compact: {acc_diff:+.1f} pkt względem JSON przy "
        "{tok_diff:.1f}% mniejszym prompcie ({eff:.1f} vs {eff_json:.1f} poprawnych "
        "odpowiedzi na 10 tys. tokenów).",
        "ai_write": "Generowanie: wynik w AK-Data dekodował się poprawnie w {w}% prób "
        "(JSON {wj}%).",
        "dry": "AI benchmark uruchomiony na sucho (bez modelu): tylko rozmiary "
        "promptów — JSON {j} vs AK-Data {a} tokenów. Trafność nie jest jeszcze "
        "zmierzona.",
        "none_ai": "Brak wyników AI benchmarku; uruchom `make benchmark MODEL=...`, "
        "żeby zmierzyć rozumienie.",
        "rec_go": "Rekomendacja: używać AK-Data compact dla danych czytanych przez "
        "model; trafność nie jest niższa od JSON o więcej niż 2 pkt.",
        "rec_wait": "Rekomendacja: przejrzeć błędne odpowiedzi przed przejściem — "
        "trafność jest niższa od JSON o ponad 2 pkt.",
        "fewer": "mniej",
        "more": "więcej",
    },
}


def auto_summary(f: Dict[str, Any], lang: str = "en") -> str:
    """A summary computed from the numbers (used when no model is available)."""
    t = _T.get(lang, _T["en"])
    parts: List[str] = []

    def num(x: int) -> str:
        return f"{x:,}".replace(",", "\u00a0" if lang == "pl" else ",")

    for b in f["token_benchmarks"]:
        totals = b["totals"]
        if "akcd" not in totals or "json" not in totals:
            continue
        rival = b["best_rival"]
        diff = b["akcd_vs_best_rival_pct"] or 0.0
        parts.append(
            t["tok"].format(
                n=b["datasets"],
                src=b["source"],
                tokz=b["tokenizer"] + ("" if b["exact_tokens"] else " ~"),
                akcd=num(totals["akcd"]),
                vs_json=abs(b["vs_json_pct"].get("akcd", 0.0)),
                vs_rival=abs(diff),
                dir=t["fewer"] if diff < 0 else t["more"],
                rival=LABELS.get(rival, rival),
            )
            + " "
            + t["wins"].format(w=b["wins"].get("akcd", 0), n=b["datasets"])
        )
        if b["datasets_where_akdata_loses"]:
            items = ", ".join(
                f"{x['dataset']} ({LABELS.get(x['winner'], x['winner'])}, "
                f"+{x['gap_pct']}%)"
                for x in b["datasets_where_akdata_loses"]
            )
            parts.append("- " + t["loses"].format(items=items))
        parts.append(
            "- "
            + (
                t["lossy"].format(items=", ".join(b["lossy_formats"]))
                if b["lossy_formats"]
                else t["lossless"]
            )
        )
    measured = [a for a in f["ai_benchmarks"] if not a["dry_run"]]
    dry = [a for a in f["ai_benchmarks"] if a["dry_run"]]
    rec_ok = []
    for a in measured:
        fm = a["formats"]
        items = ", ".join(
            f"{LABELS.get(k, k)} {v['accuracy_pct']}%"
            for k, v in fm.items()
            if v["accuracy_pct"] is not None
        )
        parts.append(t["ai"].format(model=a["model"] or a["provider"], items=items))
        if "akcd" in fm and "json" in fm and fm["json"]["accuracy_pct"] is not None:
            ak, js = fm["akcd"], fm["json"]
            acc_diff = ak["accuracy_pct"] - js["accuracy_pct"]
            rec_ok.append(acc_diff >= -2)
            parts.append(
                "- "
                + t["ai_cmp"].format(
                    acc_diff=acc_diff,
                    tok_diff=abs(_pct(ak["prompt_tokens"], js["prompt_tokens"])),
                    eff=ak["correct_per_10k_tokens"] or 0,
                    eff_json=js["correct_per_10k_tokens"] or 0,
                )
            )
            if ak["write_valid_pct"] is not None:
                parts.append(
                    "- "
                    + t["ai_write"].format(
                        w=ak["write_valid_pct"], wj=js["write_valid_pct"]
                    )
                )
    if not measured:
        if dry and "akcd" in dry[0]["formats"] and "json" in dry[0]["formats"]:
            fm = dry[0]["formats"]
            parts.append(
                t["dry"].format(
                    j=num(fm["json"]["prompt_tokens"]),
                    a=num(fm["akcd"]["prompt_tokens"]),
                )
            )
        else:
            parts.append(t["none_ai"])
    elif rec_ok:
        parts.append("**" + (t["rec_go"] if all(rec_ok) else t["rec_wait"]) + "**")
    return _join(parts)


def _join(parts: List[str]) -> str:
    """Paragraphs, with consecutive '- ' items kept together as one list."""
    out: List[str] = []
    for p in parts:
        if p.startswith("- ") and out and out[-1].startswith("- "):
            out[-1] += "\n" + p
        else:
            out.append(p)
    return "\n\n".join(out)


SUMMARY_SYSTEM = (
    "You are a precise technical analyst. You write short, factual summaries of "
    "benchmark results for engineers. Use only the numbers you are given; do not "
    "invent results; say plainly where AK-Data loses or where data is missing."
)


def ai_summary(f: Dict[str, Any], provider, lang: str = "en") -> str:
    """Asks a model to summarize the facts (passed to it in AK-Data)."""
    import arkadia.data as akd

    language = {"pl": "Polish", "en": "English"}.get(lang, lang)
    user = (
        f"{akd.HINT}\n<results>\n{akd.dumps(f)}\n</results>\n\n"
        "These are results of comparing data formats for LLM prompts: token "
        "counts per format (lower is better; vs_json_pct is the change against "
        "pretty JSON) and, if present, AI comprehension benchmarks (accuracy of a "
        "model answering questions about the same data in each format; dry_run "
        "means no model was called).\n\n"
        f"Write the summary in {language}, in Markdown, 150-250 words: "
        "1) a two-sentence headline result; 2) 3-5 bullet points with the key "
        "numbers, including where AK-Data loses; 3) a one-sentence recommendation "
        "for using AK-Data in AI agents (tool results, memory), conditional on the "
        "accuracy data if it is missing. No title."
    )
    reply = provider.complete(SUMMARY_SYSTEM, user, max_tokens=700)
    return reply.text.strip()


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------


_BULLET = re.compile(r"^\s*([-*]|\d+\.)\s+")


def _md(text: str) -> str:
    """Tiny Markdown subset → HTML (paragraphs, lists, bold, italics, code)."""

    def inline(s: str) -> str:
        s = html.escape(s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", s)
        return s

    blocks = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [ln.rstrip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        if all(re.match(r"\s*([-*]|\d+\.)\s+", ln) for ln in lines):
            items = "".join(
                "<li>" + inline(_BULLET.sub("", ln)) + "</li>" for ln in lines
            )
            blocks.append(f"<ul>{items}</ul>")
        elif lines[0].startswith("#"):
            blocks.append(f"<h3>{inline(lines[0].lstrip('# '))}</h3>")
            if lines[1:]:
                blocks.append(f"<p>{inline(' '.join(lines[1:]))}</p>")
        else:
            blocks.append(f"<p>{inline(' '.join(lines))}</p>")
    return "\n".join(blocks)


def _bars(items: List[Tuple[str, str, float, str]], unit: str = "tok") -> str:
    """Horizontal bar chart as inline SVG: (key, label, value, note)."""
    if not items:
        return ""
    top = max(v for _, _, v, _ in items) or 1
    row, label_w, bar_w = 30, 150, 420
    h = row * len(items) + 6
    out = [
        f'<svg class="bars" viewBox="0 0 {label_w + bar_w + 190} {h}" role="img" '
        f'aria-label="bar chart">'
    ]
    for i, (key, label, value, note) in enumerate(items):
        y = i * row + 4
        w = max(2, value / top * bar_w)
        out.append(
            f'<text x="0" y="{y + 16}" class="bl">{html.escape(label)}</text>'
            f'<rect x="{label_w}" y="{y + 3}" width="{w:.1f}" height="18" rx="4" '
            f'fill="{COLORS.get(key, "#888")}"/>'
            f'<text x="{label_w + w + 8:.1f}" y="{y + 16}" class="bv">'
            f"{value:,.0f}{'' if unit == '%' else ' '}{unit}"
            f'<tspan class="bn"> {html.escape(note)}</tspan></text>'
        )
    out.append("</svg>")
    return "".join(out)


CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#6b6a64;--line:#e4e1d8;--card:#fff;--accent:#1f8a4c;--warn:#b4541a;--code:#f2efe7}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--fg:#ecebe6;--muted:#a3a29b;--line:#2c2b28;--card:#1c1c1a;--accent:#4cc282;--warn:#f0a070;--code:#24231f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1040px;margin:0 auto;padding:40px 16px 80px}
h1{font-size:2.1rem;letter-spacing:-.02em;margin:.2em 0}h2{font-size:1.3rem;margin:2.2em 0 .6em;padding-bottom:.3em;border-bottom:1px solid var(--line)}h3{font-size:1.05rem;margin:1.4em 0 .4em}
.kicker{font:600 12px/1 ui-monospace,Menlo,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--accent)}
.meta{color:var(--muted);font-size:.88rem}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:18px 0}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}.stat .v{font-size:1.6rem;font-weight:700;color:var(--accent)}.stat .l{font-size:.82rem;color:var(--muted)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 20px;margin:12px 0}
.summary .src{font:600 11px/1 ui-monospace,monospace;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin-bottom:8px}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.88rem;margin:8px 0}
th,td{border-bottom:1px solid var(--line);padding:6px 9px;text-align:right;white-space:nowrap}th:first-child,td:first-child{text-align:left}
th{font-weight:600;background:var(--code)}td.best{color:var(--accent);font-weight:700}td.bad{color:var(--warn);font-weight:600}pre.test{white-space:pre-wrap;word-break:break-word;max-height:24rem;overflow:auto;background:var(--code);padding:10px;border-radius:6px;font-size:.78rem}.prompts details{margin:4px 0 4px 12px}
code,pre{font-family:ui-monospace,Menlo,monospace;font-size:.86em;background:var(--code);border-radius:5px}code{padding:.1em .3em}pre{padding:12px;overflow-x:auto}
svg.bars{width:100%;max-width:780px;height:auto}svg .bl{font:600 12px ui-sans-serif,system-ui;fill:var(--fg)}svg .bv{font:12px ui-monospace,monospace;fill:var(--fg)}svg .bn{fill:var(--muted)}
.note{color:var(--muted);font-size:.86rem}.warn{color:var(--warn)}
details{margin:8px 0}summary{cursor:pointer;color:var(--muted)}
footer{margin-top:56px;padding-top:14px;border-top:1px solid var(--line);color:var(--muted);font-size:.82rem}
"""


def _esc(v: Any) -> str:
    return html.escape(str(v))


def _token_section(name: str, b: Dict[str, Any]) -> str:
    keys = list(b.get("formats", {}))
    totals = b.get("totals", {})
    savings = b.get("savings_vs_json_pct", {})
    out = [
        f"<h3>{_esc(_short(b.get('source')))} <span class='meta'>· {_esc(name)} · tokenizer "
        f"{_esc(b.get('tokenizer'))}{'' if b.get('exact_tokens') else ' (approximate)'}"
        f"</span></h3>"
    ]
    out.append(
        _bars(
            [
                (
                    k,
                    LABELS.get(k, k),
                    totals[k],
                    "" if k == "json" else f"{savings.get(k, 0):+.1f}% vs JSON",
                )
                for k in keys
                if k in totals
            ]
        )
    )
    head = "".join(f"<th>{_esc(LABELS.get(k, k))}</th>" for k in keys)
    rows = []
    for r in b.get("rows", []):
        cells = r["cells"]
        ok = [c["tokens"] for c in cells.values() if not c.get("error")]
        best = min(ok) if ok else None
        tds = []
        for k in keys:
            c = cells.get(k, {})
            if c.get("error"):
                tds.append("<td class='bad'>error</td>")
                continue
            cls = "best" if c["tokens"] == best else ""
            mark = " ⚠" if c.get("lossless") is False else ""
            tds.append(f"<td class='{cls}'>{c['tokens']:,}{mark}</td>")
        desc = (
            f"<br><span class='note'>{_esc(r['description'])}</span>"
            if r.get("description")
            else ""
        )
        rows.append(f"<tr><td>{_esc(r['dataset'])}{desc}</td>{''.join(tds)}</tr>")
    rows.append(
        "<tr><td><b>total</b></td>"
        + "".join(
            f"<td><b>{totals[k]:,}</b></td>" if k in totals else "<td>–</td>"
            for k in keys
        )
        + "</tr>"
    )
    rows.append(
        "<tr><td>vs JSON</td>"
        + "".join(
            f"<td>{savings[k]:+.1f}%</td>" if k in savings else "<td>–</td>"
            for k in keys
        )
        + "</tr>"
    )
    out.append(
        f"<div class='scroll'><table><tr><th>dataset</th>{head}</tr>{''.join(rows)}</table></div>"
    )
    # timing
    timing_rows = []
    for k in keys:
        enc = [
            r["cells"][k]["encode_ms"]
            for r in b.get("rows", [])
            if k in r["cells"] and not r["cells"][k].get("error")
        ]
        dec = [
            r["cells"][k]["decode_ms"]
            for r in b.get("rows", [])
            if k in r["cells"] and r["cells"][k].get("decode_ms") is not None
        ]
        if any(enc):
            timing_rows.append(
                f"<tr><td>{_esc(LABELS.get(k, k))}</td><td>{sum(enc):.2f}</td>"
                f"<td>{sum(dec):.2f}</td></tr>"
            )
    if timing_rows:
        out.append(
            "<details><summary>Encode / decode time (sum over datasets, median of runs, ms)</summary>"
            "<div class='scroll'><table><tr><th>format</th><th>encode ms</th><th>decode ms</th></tr>"
            + "".join(timing_rows)
            + "</table></div></details>"
        )
    lossy = sorted(
        {
            k
            for r in b.get("rows", [])
            for k, c in r["cells"].items()
            if c.get("lossless") is False
        }
    )
    out.append(
        f"<p class='note{' warn' if lossy else ''}'>"
        + (
            "⚠ Did not decode back to the original: " + ", ".join(map(_esc, lossy))
            if lossy
            else "Fidelity: every format decoded back to the original data."
        )
        + "</p>"
    )
    return "\n".join(out)


def _ai_section(name: str, a: Dict[str, Any]) -> str:
    s = a.get("summary", {})
    keys = [k for k in a.get("formats", {}) if k in s]
    who = (
        "dry run — no model called"
        if a.get("dry_run")
        else f"{a.get('provider')} · {a.get('model')}"
    )
    nq = sum(len(v) for v in a.get("questions", {}).values())
    out = [
        f"<h3>{_esc(who)} <span class='meta'>· {_esc(name)} · {nq} questions · hint "
        f"{_esc(a.get('hint'))} · {_esc(_short(a.get('source')))}</span></h3>"
    ]
    measured = not a.get("dry_run")
    best_acc = max((s[k]["accuracy"] or 0) for k in keys) if keys and measured else None
    least = min(s[k]["prompt_tokens"] for k in keys) if keys else None
    rows = []
    for k in keys:
        r = s[k]
        acc = "–" if r["accuracy"] is None else f"{r['accuracy'] * 100:.1f}%"
        acc_cls = "best" if measured and r["accuracy"] == best_acc else ""
        tok_cls = "best" if r["prompt_tokens"] == least else ""
        eff = (
            "–"
            if r["correct_per_10k_tokens"] is None
            else f"{r['correct_per_10k_tokens']:.1f}"
        )
        wv = "–" if r.get("write_valid") is None else f"{r['write_valid'] * 100:.0f}%"
        correct = f"{r['correct']}/{r['questions']}" if measured else "–"
        ci = (
            f"{r['ci95'][0] * 100:.1f}–{r['ci95'][1] * 100:.1f}%"
            if r.get("ci95")
            else "–"
        )
        rows.append(
            f"<tr><td>{_esc(LABELS.get(k, k))}</td><td class='{acc_cls}'>{acc}</td><td>{ci}</td><td>{correct}</td>"
            f"<td class='{tok_cls}'>{r['prompt_tokens']:,}</td><td>{r['data_tokens']:,}</td>"
            f"<td>{eff}</td><td>{wv}</td></tr>"
        )
    out.append(
        "<div class='scroll'><table><tr><th>format</th><th>accuracy</th><th>95% CI</th><th>correct</th>"
        "<th>prompt tokens</th><th>data tokens</th><th>correct / 10k tok</th><th>writes valid</th></tr>"
        + "".join(rows)
        + "</table></div>"
    )
    if measured:
        out.append(
            _bars(
                [
                    (
                        k,
                        LABELS.get(k, k),
                        (s[k]["accuracy"] or 0) * 100,
                        f"{s[k]['prompt_tokens']:,} tok",
                    )
                    for k in keys
                ],
                unit="%",
            )
        )
        kinds = sorted({kind for k in keys for kind in s[k].get("by_kind", {})})
        if kinds:
            head = "".join(f"<th>{_esc(LABELS.get(k, k))}</th>" for k in keys)
            krows = "".join(
                f"<tr><td>{_esc(kind)}</td>"
                + "".join(
                    f"<td>{s[k]['by_kind'][kind] * 100:.0f}%</td>"
                    if kind in s[k].get("by_kind", {})
                    else "<td>–</td>"
                    for k in keys
                )
                + "</tr>"
                for kind in kinds
            )
            out.append(
                f"<details open><summary>Accuracy by question type</summary><div class='scroll'><table>"
                f"<tr><th>question type</th>{head}</tr>{krows}</table></div></details>"
            )
        misses = [
            (t["format"], t["dataset"], m)
            for t in a.get("trials", [])
            for m in t.get("misses", [])
        ]
        if misses:
            mrows = "".join(
                f"<tr><td>{_esc(LABELS.get(fmt, fmt))}</td><td>{_esc(ds)}</td>"
                f"<td style='text-align:left;white-space:normal'>{_esc(m['q'])}</td>"
                f"<td>{_esc(json.dumps(m['expected'], ensure_ascii=False))}</td>"
                f"<td>{_esc(m['got'])}</td></tr>"
                for fmt, ds, m in misses[:60]
            )
            out.append(
                f"<details><summary>Wrong answers ({len(misses)}{', first 60' if len(misses) > 60 else ''})</summary>"
                f"<div class='scroll'><table><tr><th>format</th><th>dataset</th><th style='text-align:left'>question</th>"
                f"<th>expected</th><th>got</th></tr>{mrows}</table></div></details>"
            )
    if measured:
        out.append(_tests_html(a))
    errors = [t for t in a.get("trials", []) if t.get("error")]
    if errors:
        out.append(
            f"<p class='note warn'>{len(errors)} request(s) failed, e.g. {_esc(errors[0]['error'][:200])}</p>"
        )
    return "\n".join(out)


def _tests_html(a: Dict[str, Any]) -> str:
    """Every question of every dataset: expected answer, each format's answer,
    and (open on demand) the exact prompt and the model's raw reply."""
    from .runs import build as build_run

    try:
        index, details = build_run(a)
    except Exception as exc:  # never break the report
        return f"<p class='note'>Test details unavailable: {_esc(exc)}</p>"
    fmts = list(index["formats"])
    head = "".join(f"<th>{_esc(LABELS.get(k, k))}</th>" for k in fmts)
    parts = []
    for ds in index["datasets"]:
        rows = []
        for i, q in enumerate(ds["questions"]):
            cells = []
            for k in fmts:
                r = (ds["results"].get(k) or [None] * (i + 1))[i]
                if r is None:
                    cells.append("<td>–</td>")
                    continue
                got = "" if r["ok"] and r["got"] is None else _esc(r["got"])
                mark = "✓" if r["ok"] else "✗"
                cls = "best" if r["ok"] else "bad"
                cells.append(f"<td class='{cls}' title='{got}'>{mark} {got[:30]}</td>")
            rows.append(
                f"<tr><td>{_esc(q['kind'])}</td><td style='text-align:left;white-space:normal'>{_esc(q['text'])}</td>"
                f"<td>{_esc(json.dumps(q['expected'], ensure_ascii=False))[:60]}</td>{''.join(cells)}</tr>"
            )
        right = sum(1 for k in fmts for r in ds["results"].get(k, []) if r["ok"])
        total = sum(len(ds["results"].get(k, [])) for k in fmts)
        prompts = []
        for k in fmts:
            d = details.get(ds["name"], {}).get(k)
            if not d:
                continue
            prompt = (
                d.get("prompt")
                or "(prompt not recorded and could not be rebuilt exactly)"
            )
            reply = d.get("reply")
            reply = (
                reply
                if reply is not None
                else "(raw reply not recorded in this run — only wrong answers were kept)"
            )
            prompts.append(
                f"<details><summary>{_esc(LABELS.get(k, k))} · {d.get('prompt_tokens') or '–'} prompt tokens</summary>"
                f"<p class='note'>system</p><pre class='test'>{_esc(index['system'])}</pre>"
                f"<p class='note'>user</p><pre class='test'>{_esc(prompt)}</pre>"
                f"<p class='note'>model reply</p><pre class='test'>{_esc(reply)}</pre></details>"
            )
        parts.append(
            f"<details><summary>{_esc(ds['name'])} · {len(ds['questions'])} questions · {right}/{total} right</summary>"
            f"<div class='scroll'><table><tr><th>type</th><th style='text-align:left'>question</th><th>expected</th>{head}</tr>"
            f"{''.join(rows)}</table></div><div class='prompts'>{''.join(prompts)}</div></details>"
        )
    note = {
        "recorded": "prompts and raw replies as sent and received",
        "rebuilt": "prompts rebuilt exactly from the data (same token counts); this run did not record raw replies",
        "missing": "prompts not available for this run",
    }[index["prompts"]]
    return (
        f"<details><summary>Every test ({len(index['datasets'])} datasets) — {note}</summary>"
        + "".join(parts)
        + "</details>"
    )


def render(
    inputs: Inputs,
    summary: str,
    summary_source: str,
    title: str = "AK-Data benchmark report",
) -> str:
    import arkadia.data as akd

    f = facts(inputs)
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    stats = []
    if f["token_benchmarks"]:
        b = f["token_benchmarks"][0]
        if "akcd" in b["vs_json_pct"]:
            stats.append(
                (
                    f"{b['vs_json_pct']['akcd']:+.1f}%",
                    "AK-Data compact vs JSON (tokens)",
                )
            )
        if b["akcd_vs_best_rival_pct"] is not None:
            stats.append(
                (
                    f"{b['akcd_vs_best_rival_pct']:+.1f}%",
                    f"vs {LABELS.get(b['best_rival'], b['best_rival'])}, the best alternative",
                )
            )
        stats.append(
            (
                f"{b['wins'].get('akcd', 0)}/{b['datasets']}",
                "datasets with the fewest tokens",
            )
        )
        stats.append(
            ("yes" if not b["lossy_formats"] else "no", "all formats lossless")
        )
    measured = [a for a in f["ai_benchmarks"] if not a["dry_run"]]
    for a in measured[:2]:
        fm = a["formats"]
        if "akcd" in fm and fm["akcd"]["accuracy_pct"] is not None:
            js = fm.get("json", {}).get("accuracy_pct")
            stats.append(
                (
                    f"{fm['akcd']['accuracy_pct']}%",
                    f"AK-Data accuracy · {a['model']}"
                    + (f" (JSON {js}%)" if js is not None else ""),
                )
            )
    stat_html = "".join(
        f"<div class='stat'><div class='v'>{_esc(v)}</div><div class='l'>{_esc(label)}</div></div>"
        for v, label in stats
    )
    token_html = (
        "\n".join(_token_section(n, b) for n, b in inputs.benchmarks)
        or "<p class='note'>No token benchmark results found. Run <code>make benchmark</code>.</p>"
    )
    ai_html = (
        "\n".join(_ai_section(n, a) for n, a in inputs.ai)
        or "<p class='note'>No AI benchmark results found. Run <code>make benchmark MODEL=…</code>.</p>"
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title><style>{CSS}</style></head>
<body><main>
<div class="kicker">AK-Data (Arkadia Data Format) {akd.__version__} · report</div>
<h1>{_esc(title)}</h1>
<p class="meta">Generated {now} · Python {platform.python_version()} · {len(inputs.benchmarks)} token benchmark(s), {len(inputs.ai)} AI benchmark(s)</p>
<div class="grid">{stat_html}</div>

<h2>Summary</h2>
<div class="card summary"><div class="src">{_esc(summary_source)}</div>{_md(summary)}</div>

<h2>Tokens, speed and fidelity</h2>
{token_html}

<h2>AI comprehension</h2>
<p class="note">Questions with known answers are generated from each dataset (lookups, positions, nested paths, counts with one or two conditions, maxima and minima, filters, sums, optional fields, list lengths, field names) and asked with the data in each format; answers are scored exactly. Generated datasets (--random) add questions; the 95% interval shows how far the accuracy could move with another sample. "Correct / 10k tok" combines accuracy and cost.</p>
{ai_html}

<h2>Method and reproduction</h2>
<ul>
<li>Token counts: tiktoken encodings when available, otherwise a calibrated estimate (marked approximate).</li>
<li>Fidelity: every encoding is decoded and compared with the original; ⚠ marks a format that did not round-trip.</li>
<li>Timing: median of repeated runs on this machine; pure-Python AK-Data is slower than C-backed JSON.</li>
</ul>
<pre>make benchmark                         # tokens → AI (dry run without a key) → this file
make benchmark MODEL=gpt-4o-mini       # with a model (OPENAI_API_KEY / ANTHROPIC_API_KEY)
make benchmark ONLY_SHOW=1             # only print the prompts</pre>
<footer>AK-Data — Arkadia Data Format · arkadia-data (PyPI) · @arkadia/data (npm) · MIT · Arkadia Solutions</footer>
</main></body></html>
"""


def build(
    inputs_paths: List[pathlib.Path],
    out: pathlib.Path,
    provider=None,
    lang: str = "en",
    title: str = "AK-Data benchmark report",
) -> Tuple[pathlib.Path, str]:
    """Builds the report; returns (path, summary source)."""
    inputs = load_inputs(inputs_paths)
    f = facts(inputs)
    source = "Summary generated from the numbers (no model configured)"
    summary = auto_summary(f, lang)
    if provider is not None:
        try:
            summary = ai_summary(f, provider, lang)
            source = f"Summary written by {provider.name} · {provider.model} from the numbers below"
        except Exception as exc:  # fall back, but say so
            source = f"Summary generated from the numbers (model call failed: {str(exc)[:120]})"
    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(inputs, summary, source, title), encoding="utf-8")
    (out.with_suffix(".summary.md")).write_text(summary + "\n", encoding="utf-8")
    return out, source
