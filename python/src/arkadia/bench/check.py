"""
`make check` — metadata traps on real models.

Five small tables whose numbers mean something a model cannot guess (a reversed
sign, a unit in grosze, an error code 999.9, a test record …), each sent in four
forms (examples/meta-traps/cases.md):

    A  JSON                     no notes
    B  JSON-meta                a "_meta" object with notes per field
    C  AK-Data                  no notes
    D  AK-Data + comments       /* comments */ (on schema, fields, or single records) and //$size=N//

to OpenAI, Anthropic and Google models. For every answer the script prints, in
colour, whether it is right (✓), a known trap (✗ trap — the model relied on habit
instead of the notes), some other wrong answer (✗) or an error (!), and ends with
a summary: score per model and form, how much the notes help in JSON and in
AK-Data, prompt tokens, and the cases a form with notes still got wrong.

    python -m arkadia.bench.check                         # every provider with a key in .env
    python -m arkadia.bench.check openai google           # only these providers
    python -m arkadia.bench.check --cases 1,4 --forms B,D # a subset
    python -m arkadia.bench.check --demo                  # no API calls: invented answers, to see the output
    python -m arkadia.bench.check --dry-run               # no API calls: check the cases, count tokens
    python -m arkadia.bench.check --show 4                # print the four prompts of case 4 (or: all)
    python -m arkadia.bench.check --copy 4D               # put prompt 4D on the clipboard (to paste into ChatGPT)
    python -m arkadia.bench.check --no-prompts            # results only, without the prompts

Every case is printed with its four prompts first — exactly the text sent to the
models, ready to copy into ChatGPT, Claude or Gemini by hand — and then the
answers. The prompts are also written as files: reports/prompts/<case><form>.txt
(one prompt per file) and reports/prompts/all.md (all of them with the answers).

Keys come from the environment or .env (searched upward from the current folder):
OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY (Gemini through Google's
OpenAI-compatible endpoint). Models: OPENAI_MODEL, ANTHROPIC_MODEL, GOOGLE_MODEL,
or --model provider=name (repeatable; several models per provider with commas).
The full report — every prompt, raw reply and verdict — goes to
reports/check-<date>.json. Model calls cost money: 20 calls per model.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import pathlib
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple

from arkadia.data import loads as akd_loads
from arkadia.data.tokens import get_tokenizer

from .ai_bench import Anthropic, OpenAICompatible, Provider, Reply, Scripted

FORMS = {"A": "JSON", "B": "JSON-meta", "C": "AK-Data", "D": "AK-Data+meta"}
FORM_HAS_META = {"A": False, "B": True, "C": False, "D": True}
SYSTEM = "Check each record, then write only the final answer last."
DEFAULT_MODELS = {
    "openai": "gpt-5.4-mini",
    "anthropic": "claude-haiku-5-5",
    "google": "gemini-3.5-flash-lite",
}
KEYS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
}
GOOGLE_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"


def default_cases_file() -> pathlib.Path:
    here = pathlib.Path(__file__).resolve()
    for up in [*here.parents, pathlib.Path.cwd(), *pathlib.Path.cwd().parents]:
        p = up / "examples" / "meta-traps" / "cases.md"
        if p.exists():
            return p
    return pathlib.Path("examples/meta-traps/cases.md")


# ---------------------------------------------------------------- colours


class Paint:
    def __init__(self, on: bool):
        self.on = on

    def __call__(self, text: str, *codes: str) -> str:
        if not self.on or not codes:
            return text
        return "".join(f"\033[{c}m" for c in codes) + text + "\033[0m"

    def ok(self, t: str) -> str:
        return self(t, "1", "38;5;40")

    def trap(self, t: str) -> str:
        return self(t, "1", "38;5;203")

    def wrong(self, t: str) -> str:
        return self(t, "38;5;214")

    def err(self, t: str) -> str:
        return self(t, "38;5;244")

    def dim(self, t: str) -> str:
        return self(t, "2")

    def bold(self, t: str) -> str:
        return self(t, "1")

    def form(self, f: str, t: str) -> str:
        return self(
            t, "1", {"A": "38;5;39", "B": "38;5;75", "C": "38;5;34", "D": "38;5;46"}[f]
        )


def visible_len(s: str) -> int:
    return len(re.sub(r"\033\[[0-9;]*m", "", s))


def pad(s: str, width: int) -> str:
    return s + " " * max(0, width - visible_len(s))


# ---------------------------------------------------------------- cases


@dataclass
class Case:
    num: int
    title: str
    expected: List[str]
    traps: List[str]
    prompts: Dict[str, str]  # form letter -> full prompt
    data: Dict[str, str] = field(default_factory=dict)  # form letter -> data block


def parse_cases(text: str) -> List[Case]:
    """Cases from cases.md: headings, Expected / Trap lines and ```text blocks."""
    cases: List[Case] = []
    parts = re.split(r"^## (\d+)\. (.+)$", text, flags=re.M)
    for i in range(1, len(parts), 3):
        num, title, body = int(parts[i]), parts[i + 1].strip(), parts[i + 2]
        exp = re.search(r"\*\*Expected Answer:\*\*(.*)", body)
        traps = re.search(r"\*\*Trap Answers[^*]*\*\*(.*)", body)
        if not exp:
            raise ValueError(f"case {num}: no 'Expected Answer' line")
        prompts: Dict[str, str] = {}
        data: Dict[str, str] = {}
        for letter, block in re.findall(
            r"\*\*Prompt \d+([A-D])[^*]*\*\*\s*```text\n(.*?)```", body, flags=re.S
        ):
            prompts[letter] = block.strip()
            m = re.search(r"Data:\n(.*?)\n\s*\nQuestion:", block, flags=re.S)
            data[letter] = m.group(1).strip() if m else ""
        missing = [f for f in FORMS if f not in prompts]
        if missing:
            raise ValueError(f"case {num}: no prompt for {', '.join(missing)}")
        cases.append(
            Case(
                num,
                title,
                re.findall(r"`([^`]+)`", exp.group(1)),
                re.findall(r"`([^`]+)`", traps.group(1)) if traps else [],
                prompts,
                data,
            )
        )
    if not cases:
        raise ValueError("no cases found (expected '## 1. Title' headings)")
    return cases


def validate(cases: List[Case]) -> List[str]:
    """The four forms of a case must carry the same data; AK-Data must decode."""
    problems: List[str] = []
    for c in cases:
        decoded: Dict[str, object] = {}
        for f in FORMS:
            raw = c.data.get(f, "")
            if not raw:
                problems.append(f"{c.num}{f}: no 'Data:' block")
                continue
            try:
                value = json.loads(raw) if f in "AB" else akd_loads(raw)
            except Exception as exc:  # noqa: BLE001 — any parse error is reported
                problems.append(
                    f"{c.num}{f}: {'JSON' if f in 'AB' else 'AK-Data'} does not parse: {str(exc)[:160]}"
                )
                continue
            if f == "B" and isinstance(value, dict):
                value = {k: v for k, v in value.items() if k != "_meta"}
            decoded[f] = value
        base = decoded.get("A")
        for f in "BCD":
            if base is not None and f in decoded and decoded[f] != base:
                problems.append(f"{c.num}{f}: data differs from {c.num}A (JSON)")
    return problems


# ---------------------------------------------------------------- scoring


_NUM = re.compile(r"^[+-]?\d[\d,_ ]*(?:\.\d+)?$|^[+-]?\.\d+$")


def clean_answer(reply: str) -> str:
    lines = [line.strip() for line in reply.strip().splitlines() if line.strip()]
    s = lines[-1] if lines else ""
    s = re.sub(
        r"^\s*(?:final\s+answer|answer|result|total|balance)\s*[:=]\s*",
        "",
        s,
        flags=re.I,
    )
    if "=" in s:
        s = s.rsplit("=", 1)[-1]
    s = s.strip().strip("`*\"'").strip()
    s = re.sub(r"^(?:EUR|PLN|USD|JPY|€|\$)\s*(?=[+-]?\d)", "", s, flags=re.I)
    s = re.sub(r"[.\s]+$", "", s)
    s = re.sub(
        r"\s*(?:PLN|EUR|USD|JPY|€|cents?|bars?|decibars?|units?|pallets?|vCPU-hours?|vcpu-hours?|patients?|tickets?)\b\.?$",
        "",
        s,
        flags=re.I,
    )
    return s.strip().strip("`*\"'").rstrip(".").strip()


def _num(s: str) -> Optional[float]:
    s = s.strip()
    if not _NUM.match(s):
        return None
    t = s.replace("_", "").replace(" ", "")
    if "," in t and "." not in t and re.fullmatch(r"[+-]?\d{1,3}(,\d{3})+", t):
        t = t.replace(",", "")
    elif "," in t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def same(answer: str, target: str) -> bool:
    a, b = _num(answer), _num(target)
    if a is not None and b is not None:
        return abs(a - b) <= 1e-6 * max(1.0, abs(b))
    if "," in target or "," in answer:
        sa = {x.strip().lower() for x in answer.split(",") if x.strip()}
        sb = {x.strip().lower() for x in target.split(",") if x.strip()}
        return sa == sb
    return answer.strip().lower() == target.strip().lower()


def verdict(case: Case, answer: str) -> str:
    if any(same(answer, e) for e in case.expected):
        return "ok"
    if any(same(answer, t) for t in case.traps):
        return "trap"
    return "wrong"


# ---------------------------------------------------------------- providers


def env_files() -> List[pathlib.Path]:
    """Every .env from the current folder upward, then above this file (the repository
    root); nearest first. An empty or partial python/.env does not hide the root one."""
    seen: List[pathlib.Path] = []
    here = pathlib.Path(__file__).resolve()
    for up in [pathlib.Path.cwd(), *pathlib.Path.cwd().parents, *here.parents]:
        env = (up / ".env").resolve()
        if env.is_file() and env not in seen:
            seen.append(env)
    return seen


def load_env() -> List[pathlib.Path]:
    """Loads every .env (env_files); a variable already set is never overwritten."""
    files = env_files()
    for env in files:
        try:
            from dotenv import load_dotenv

            load_dotenv(env, override=False)
            continue
        except Exception:  # noqa: BLE001 — python-dotenv is optional
            pass
        for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"^\s*(?:export\s+)?([A-Za-z_]\w*)\s*=\s*(.*)$", line)
            if m and m.group(1) not in os.environ:
                os.environ[m.group(1)] = m.group(2).strip().strip("'\"")
    return files


def make_provider(provider: str, model: str, reasoning: Optional[str]) -> Provider:
    if provider == "openai":
        p: Provider = OpenAICompatible(model, reasoning=reasoning or "low")
    elif provider == "anthropic":
        p = Anthropic(model)
    elif provider == "google":
        p = OpenAICompatible(
            model,
            api_key=os.environ.get("GOOGLE_API_KEY", ""),
            base_url=GOOGLE_BASE,
            reasoning=reasoning,
        )
    else:
        raise ValueError(f"unknown provider '{provider}' (openai, anthropic, google)")
    p.name = provider  # type: ignore[misc]
    return p


def demo_provider(cases: List[Case], name: str, model: str, skill: int) -> Provider:
    """Invented answers that look like a real run (for --demo)."""
    by_prompt = {c.prompts[f]: (c, f) for c in cases for f in FORMS}

    def answer(_system: str, user: str) -> str:
        c, f = by_prompt[user.strip()]
        h = (c.num * 7 + ord(f) * 3 + skill * 5) % 10
        if FORM_HAS_META[f]:
            return (
                c.expected[0]
                if h < 8 + (f == "D")
                else (c.traps[0] if c.traps else "0")
            )
        return (
            c.traps[h % len(c.traps)]
            if c.traps and h < 8
            else c.expected[0]
            if h == 9
            else "42"
        )

    s = Scripted(answer, model=model)
    s.name = name  # type: ignore[misc]
    return s


# ---------------------------------------------------------------- running


@dataclass
class Result:
    provider: str
    model: str
    case: int
    form: str
    trial: int
    prompt_tokens: int
    reply: str = ""
    answer: str = ""
    verdict: str = "error"  # ok | trap | wrong | error
    error: Optional[str] = None
    seconds: float = 0.0
    api_input_tokens: Optional[int] = None


def run_one(p: Provider, case: Case, form: str, trial: int, tokens: int) -> Result:
    r = Result(p.name, p.model, case.num, form, trial, tokens)
    t0 = time.perf_counter()
    try:
        reply: Reply = p.complete(SYSTEM, case.prompts[form], max_tokens=1000)
        r.reply = reply.text
        r.api_input_tokens = reply.input_tokens
        r.answer = clean_answer(reply.text)
        r.verdict = verdict(case, r.answer)
    except Exception as exc:  # noqa: BLE001 — every failure is shown, the run goes on
        r.error = str(exc)[:500]
    r.seconds = round(time.perf_counter() - t0, 2)
    return r


# ---------------------------------------------------------------- printing

SYM = {"ok": "✓", "trap": "✗", "wrong": "✗", "error": "!"}


def cell(paint: Paint, r: Optional[Result], width: int) -> str:
    if r is None:
        return pad(paint.dim("·"), width)
    if r.verdict == "error":
        return pad(paint.err("! error"), width)
    ans = r.answer if len(r.answer) <= width - 9 else r.answer[: width - 10] + "…"
    ans = ans or "(empty)"
    if r.verdict == "ok":
        return pad(paint.ok(f"✓ {ans}"), width)
    if r.verdict == "trap":
        return pad(paint.trap(f"✗ {ans}") + paint.trap(" trap"), width)
    return pad(paint.wrong(f"✗ {ans}"), width)


def bar(paint: Paint, share: float, width: int = 12) -> str:
    full = round(share * width)
    color = "38;5;40" if share >= 0.8 else "38;5;214" if share >= 0.5 else "38;5;203"
    return paint("█" * full, color) + paint.dim("░" * (width - full))


def print_prompts(
    paint: Paint, case: Case, forms: List[str], tokens: Dict[tuple, int]
) -> None:
    """The prompts exactly as sent: only the frame is coloured, the text between the lines copies clean."""
    for f in forms:
        head = f"┌─ {case.num}{f} · {FORMS[f]} · {tokens.get((case.num, f), 0)} tokens "
        print("    " + paint.form(f, head + "─" * max(4, 74 - len(head))))
        print(case.prompts[f])
        print("    " + paint.form(f, "└" + "─" * 73))


def case_header(paint: Paint, case: Case) -> None:
    print()
    print(paint.bold(f"{case.num:>2}. {case.title}"))
    traps = " | ".join(case.traps) or "—"
    print(
        f"    expected {paint.ok(' or '.join(case.expected))}   {paint.dim('traps without notes:')} {paint.trap(traps) if case.traps else traps}"
    )


def print_case(
    paint: Paint,
    case: Case,
    models: List[Tuple[str, str]],
    forms: List[str],
    res: Dict[tuple, List[Result]],
    prompts: Optional[Dict[tuple, int]] = None,
) -> None:
    w = 20
    case_header(paint, case)
    if prompts is not None:
        print_prompts(paint, case, forms, prompts)
        print(paint.bold("    Answers"))
    label_w = max(24, *(len(f"{p} {m}") + 2 for p, m in models))
    print(
        "    "
        + pad(paint.dim("model"), label_w)
        + "".join(pad(paint.form(f, FORMS[f]), w) for f in forms)
    )
    for p, m in models:
        line = "    " + pad(f"{paint.bold(p)} {paint.dim(m)}", label_w)
        for f in forms:
            rs = res.get((p, m, case.num, f), [])
            if len(rs) <= 1:
                line += cell(paint, rs[0] if rs else None, w)
            else:
                good = sum(r.verdict == "ok" for r in rs)
                txt = f"{good}/{len(rs)} " + "".join(SYM[r.verdict] for r in rs)
                line += pad(
                    paint.ok(txt)
                    if good == len(rs)
                    else paint.trap(txt)
                    if not good
                    else paint.wrong(txt),
                    w,
                )
        print(line)
    errors = [
        r for (p, m, n, f), rs in res.items() if n == case.num for r in rs if r.error
    ]
    for r in errors[:3]:
        print(paint.err(f"    ! {r.provider} {r.form}: {r.error[:150]}"))


def summary(
    paint: Paint,
    cases: List[Case],
    models: List[Tuple[str, str]],
    forms: List[str],
    results: List[Result],
    tokens: Dict[str, int],
) -> None:
    def score(sel) -> Tuple[int, int, int, int]:
        rs = [r for r in results if sel(r)]
        return (
            sum(r.verdict == "ok" for r in rs),
            len(rs),
            sum(r.verdict == "trap" for r in rs),
            sum(r.verdict == "error" for r in rs),
        )

    print()
    print(paint.bold("━" * 78))
    print(
        paint.bold("  SUMMARY")
        + paint.dim(
            f"   {len(cases)} cases · {len(models)} model(s) · {len(results)} answers"
        )
    )
    print(paint.bold("━" * 78))

    # 1. score per model and form
    print()
    print(
        paint.bold("  Correct answers per model and form")
        + paint.dim("   (✗ trap = the model followed habit instead of the notes)")
    )
    label_w = max(24, *(len(f"{p} {m}") + 2 for p, m in models))
    print(
        "    "
        + pad("", label_w)
        + "".join(pad(paint.form(f, FORMS[f]), 24) for f in forms)
    )
    rows = models + ([("all", "models")] if len(models) > 1 else [])
    for p, m in rows:
        line = "    " + pad(f"{paint.bold(p)} {paint.dim(m)}", label_w)
        for f in forms:
            ok, n, tr, er = score(
                lambda r: (
                    r.form == f and (p == "all" or (r.provider == p and r.model == m))
                )
            )
            share = ok / n if n else 0
            txt = f"{ok:>3}/{n:<3}" + bar(paint, share, 8)
            extra = (paint.trap(f" {tr}✗") if tr else "") + (
                paint.err(f" {er}!") if er else ""
            )
            line += pad(f"{txt}{extra}", 24)
        print(line)

    # 2. what the notes change
    print()
    print(paint.bold("  What the notes change"))
    for plain, meta, name in (("A", "B", "JSON"), ("C", "D", "AK-Data")):
        if plain not in forms or meta not in forms:
            continue
        a, na, ta, _ = score(lambda r: r.form == plain)
        b, nb, tb, _ = score(lambda r: r.form == meta)
        if not na or not nb:
            continue
        gain = b / nb - a / na
        arrow = paint.ok(f"+{gain:.0%}") if gain > 0 else paint.trap(f"{gain:.0%}")
        print(
            f"    {pad(paint.form(plain, name), 12)} {a / na:>4.0%} → {b / nb:>4.0%}  {arrow}   traps {paint.trap(str(ta))} → {paint.trap(str(tb)) if tb else paint.ok('0')}"
        )

    # 3. AK-Data with comments vs JSON with notes
    if "B" in forms and "D" in forms:
        b, nb, _, _ = score(lambda r: r.form == "B")
        d, nd, _, _ = score(lambda r: r.form == "D")
        if nb and nd:
            tb, td = tokens.get("B", 0), tokens.get("D", 0)
            diff = (td - tb) / tb if tb else 0
            print()
            print(paint.bold("  AK-Data + comments vs JSON + _meta"))
            verdict_txt = (
                paint.ok("as good or better")
                if d / nd >= b / nb
                else paint.trap("worse")
            )
            print(
                f"    accuracy  {paint.form('D', f'{d / nd:.0%}')} vs {paint.form('B', f'{b / nb:.0%}')}  → {verdict_txt}"
            )
            print(
                f"    tokens    {paint.form('D', str(td))} vs {paint.form('B', str(tb))} per run of {len(cases)} prompts  → {paint.ok(f'{diff:+.0%}') if diff < 0 else paint.trap(f'{diff:+.0%}')}"
            )

    # 4. tokens per form
    print()
    print(
        paint.bold("  Prompt tokens")
        + paint.dim(f"   (all {len(cases)} prompts of a form, counted locally)")
    )
    base = tokens.get("A") or 1
    for f in forms:
        t = tokens.get(f, 0)
        print(
            f"    {pad(paint.form(f, FORMS[f]), 16)} {t:>6}  {paint.dim(f'{(t - base) / base:+.0%} vs JSON') if f != 'A' else paint.dim('reference')}"
        )

    # 5. what still fails with notes
    misses = [
        r for r in results if FORM_HAS_META[r.form] and r.verdict in ("trap", "wrong")
    ]
    print()
    if misses:
        print(
            paint.bold("  Still wrong with notes")
            + paint.dim("   — read these replies")
        )
        by_num = {c.num: c for c in cases}
        for r in sorted(misses, key=lambda r: (r.case, r.form, r.provider)):
            c = by_num[r.case]
            kind = paint.trap("trap") if r.verdict == "trap" else paint.wrong("wrong")
            print(
                f"    {r.case:>2}{r.form} {pad(paint.form(r.form, FORMS[r.form]), 14)} {pad(f'{r.provider} {r.model}', 30)} {kind}  {paint.dim('answered')} {r.answer!r} {paint.dim('expected')} {' or '.join(c.expected)}"
            )
    elif results:
        print(paint.ok("  Every prompt with notes was answered correctly."))
    errs = [r for r in results if r.verdict == "error"]
    if errs:
        print(
            paint.err(
                f"\n  {len(errs)} call(s) failed — see the errors above and the report."
            )
        )


# ---------------------------------------------------------------- main


def parse_models(args: argparse.Namespace) -> List[Tuple[str, str]]:
    chosen = [p.lower() for p in args.providers] or ["openai", "anthropic", "google"]
    override: Dict[str, List[str]] = {}
    for spec in args.model or []:
        if "=" not in spec:
            raise SystemExit(f"--model needs provider=name, got '{spec}'")
        prov, names = spec.split("=", 1)
        override[prov.strip().lower()] = [
            n.strip() for n in names.split(",") if n.strip()
        ]
    out: List[Tuple[str, str]] = []
    for p in chosen:
        if p not in DEFAULT_MODELS:
            raise SystemExit(f"unknown provider '{p}' (openai, anthropic, google)")
        names = override.get(p) or [
            n.strip()
            for n in os.environ.get(f"{p.upper()}_MODEL", DEFAULT_MODELS[p])
            .replace(" ", ",")
            .split(",")
            if n.strip()
        ]
        out += [(p, n) for n in names]
    return out


def write_prompts(
    cases: List[Case], forms: List[str], out: pathlib.Path
) -> pathlib.Path:
    """reports/prompts/<case><form>.txt and all.md — the prompts to test by hand."""
    folder = out / "prompts"
    folder.mkdir(parents=True, exist_ok=True)
    md = [
        "# Metadata traps — prompts to paste into a chat",
        "",
        "Each prompt is self-contained. Paste it as it is and compare the reply with the expected answer.",
        "",
    ]
    for c in cases:
        md += [
            f"## {c.num}. {c.title}",
            "",
            f"Expected: **{' or '.join(c.expected)}** · traps without notes: {' | '.join(c.traps) or '—'}",
            "",
        ]
        for f in forms:
            (
                folder / f"{c.num:02d}{f}-{FORMS[f].lower().replace('+', '-')}.txt"
            ).write_text(c.prompts[f] + "\n", encoding="utf-8")
            md += [
                f"### {c.num}{f} · {FORMS[f]}",
                "",
                "```text",
                c.prompts[f],
                "```",
                "",
            ]
    (folder / "all.md").write_text("\n".join(md), encoding="utf-8")
    return folder


def copy_to_clipboard(text: str) -> Optional[str]:
    """pbcopy (macOS), wl-copy, xclip or clip.exe; the name of the tool used, or None."""
    import shutil
    import subprocess

    for cmd in (
        ["pbcopy"],
        ["wl-copy"],
        ["xclip", "-selection", "clipboard"],
        ["clip.exe"],
    ):
        if shutil.which(cmd[0]):
            subprocess.run(cmd, input=text.encode("utf-8"), check=True)
            return cmd[0]
    return None


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m arkadia.bench.check",
        description=__doc__.split("\n\n")[0].strip(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "providers", nargs="*", help="openai anthropic google (default: all with a key)"
    )
    ap.add_argument(
        "--model",
        action="append",
        help="provider=model[,model…], e.g. openai=gpt-5.5,gpt-5.4-mini",
    )
    ap.add_argument(
        "--cases", default="", help="case numbers, e.g. 1,5,7 (default: all)"
    )
    ap.add_argument(
        "--forms",
        default="ABCD",
        help="forms to send: A JSON, B JSON-meta, C AK-Data, D AK-Data+meta",
    )
    ap.add_argument("--trials", type=int, default=1, help="repeat every prompt N times")
    ap.add_argument(
        "--parallel",
        type=int,
        default=4,
        help="calls at once per provider (Google: 1 unless set)",
    )
    ap.add_argument(
        "--reasoning",
        default=None,
        help="reasoning_effort for GPT-5 / Gemini: low | medium | high",
    )
    ap.add_argument(
        "--file",
        default=None,
        help="cases file (default: examples/meta-traps/cases.md)",
    )
    ap.add_argument("--out", default="reports", help="folder for the JSON report")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="no API calls: check the cases and count tokens",
    )
    ap.add_argument(
        "--demo",
        action="store_true",
        help="no API calls: invented answers, to see the output",
    )
    ap.add_argument(
        "--show",
        default="",
        metavar="N",
        help="print the prompts of case N (or 'all') and stop",
    )
    ap.add_argument(
        "--copy",
        default="",
        metavar="NF",
        help="copy one prompt to the clipboard, e.g. 3D, and stop",
    )
    ap.add_argument(
        "--prompts",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="print every case's prompts before its answers (default: on)",
    )
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args(argv)

    paint = Paint(
        not args.no_color
        and not os.environ.get("NO_COLOR")
        and (sys.stdout.isatty() or bool(os.environ.get("FORCE_COLOR")))
    )
    path = pathlib.Path(args.file) if args.file else default_cases_file()
    cases = parse_cases(path.read_text(encoding="utf-8"))
    if args.cases:
        want = {int(x) for x in re.split(r"[,\s]+", args.cases) if x}
        cases = [c for c in cases if c.num in want]
    forms = [f for f in args.forms.upper() if f in FORMS]

    if args.copy:
        m = re.fullmatch(r"\s*(\d+)\s*([A-Da-d])\s*", args.copy)
        c = next((c for c in cases if m and c.num == int(m.group(1))), None)
        if not m or not c:
            raise SystemExit(
                f"--copy needs a case and a form, e.g. 3D (got '{args.copy}')"
            )
        f = m.group(2).upper()
        tool = copy_to_clipboard(c.prompts[f])
        if not tool:
            print(c.prompts[f])
            print(
                paint.wrong(
                    "\n  No clipboard tool found (pbcopy, wl-copy, xclip) — the prompt is printed above."
                )
            )
            return 1
        print(
            paint.ok(f"  ✓ Prompt {c.num}{f} ({FORMS[f]}) copied with {tool}.")
            + f"  Expected {paint.ok(' or '.join(c.expected))}, traps {paint.trap(' | '.join(c.traps))}."
        )
        return 0

    if args.show:
        want = (
            cases
            if args.show.strip().lower() == "all"
            else [c for c in cases if str(c.num) in re.split(r"[,\s]+", args.show)]
        )
        if not want:
            raise SystemExit(f"no case {args.show}")
        tok = get_tokenizer()
        counts = {(c.num, f): tok.count(c.prompts[f]) for c in want for f in forms}
        for c in want:
            case_header(paint, c)
            print_prompts(paint, c, forms, counts)
        return 0

    print(paint.bold("AK-Data metadata check") + paint.dim(f"  ·  {path}"))
    problems = validate(cases)
    if problems:
        print(paint.trap(f"\n  The cases file has {len(problems)} problem(s):"))
        for p in problems:
            print(paint.trap(f"    • {p}"))
        print(
            paint.dim("  Fix them first: a prompt with broken data measures nothing.")
        )
        return 2
    print(
        paint.ok(
            f"  ✓ {len(cases)} cases · the four forms of each case carry the same data"
        )
    )

    tok = get_tokenizer()
    per_prompt = {
        (c.num, f): tok.count(SYSTEM) + tok.count(c.prompts[f])
        for c in cases
        for f in forms
    }
    tokens = {f: sum(per_prompt[(c.num, f)] for c in cases) for f in forms}
    print(
        paint.dim(f"  prompt tokens ({tok.label}): ")
        + "  ".join(f"{paint.form(f, FORMS[f])} {tokens[f]}" for f in forms)
    )

    folder = write_prompts(cases, forms, pathlib.Path(args.out))
    print(
        paint.dim(
            f"  prompts to paste by hand: {folder}/ (one .txt per prompt, all.md with every case)"
        )
    )

    if args.dry_run:
        if args.prompts:
            for c in cases:
                case_header(paint, c)
                print_prompts(paint, c, forms, per_prompt)
        print(paint.dim("\n  Dry run: no model was called."))
        return 0

    env = load_env()
    providers: List[Provider] = []
    if args.demo:
        providers = [
            demo_provider(cases, "openai", "demo-model", 1),
            demo_provider(cases, "anthropic", "demo-model", 2),
        ]
        models = [(p.name, p.model) for p in providers]
        print(
            paint.wrong("  Demo: the answers below are invented — no model was called.")
        )
    else:
        models = []
        for prov, name in parse_models(args):
            if not os.environ.get(KEYS[prov]) and not (
                prov == "openai" and os.environ.get("OPENAI_BASE_URL")
            ):
                print(
                    paint.wrong(
                        f"  – {prov} {name}: skipped, no {KEYS[prov]} in the environment or .env"
                    )
                )
                continue
            providers.append(make_provider(prov, name, args.reasoning))
            models.append((prov, name))
        if not providers:
            where = ", ".join(str(e) for e in env) or "none found"
            print(paint.dim(f"  .env files read: {where}"))
            print(
                paint.trap(
                    "\n  No model to ask. Put OPENAI_API_KEY, ANTHROPIC_API_KEY or GOOGLE_API_KEY in .env (or use --demo / --dry-run)."
                )
            )
            return 1
    calls = len(providers) * len(cases) * len(forms) * args.trials
    print(
        f"  {paint.bold(str(calls))} calls: "
        + ", ".join(f"{paint.bold(p)} {paint.dim(m)}" for p, m in models)
    )

    results: List[Result] = []
    res: Dict[tuple, List[Result]] = {}
    started = time.perf_counter()
    jobs = []
    pools = []
    for p in providers:
        workers = (
            args.parallel
            if p.name != "google" or "--parallel" in (argv or sys.argv)
            else 1
        )
        pool = ThreadPoolExecutor(max_workers=max(1, workers))
        pools.append(pool)
        for c in cases:
            for f in forms:
                for t in range(args.trials):
                    jobs.append(
                        pool.submit(run_one, p, c, f, t, per_prompt[(c.num, f)])
                    )
    done = 0
    for fut in as_completed(jobs):
        r = fut.result()
        results.append(r)
        res.setdefault((r.provider, r.model, r.case, r.form), []).append(r)
        done += 1
        if sys.stderr.isatty():
            mark = {
                "ok": paint.ok("✓"),
                "trap": paint.trap("✗"),
                "wrong": paint.wrong("✗"),
                "error": paint.err("!"),
            }[r.verdict]
            sys.stderr.write(
                f"\r  {done}/{calls} {mark} {r.provider} {r.case}{r.form}      "
            )
            sys.stderr.flush()
    for pool in pools:
        pool.shutdown()
    if sys.stderr.isatty():
        sys.stderr.write("\r" + " " * 60 + "\r")
    for lst in res.values():
        lst.sort(key=lambda r: r.trial)

    for c in cases:
        print_case(paint, c, models, forms, res, per_prompt if args.prompts else None)
    summary(paint, cases, models, forms, results, tokens)

    if not args.demo:
        out = pathlib.Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M")
        report = out / f"check-{stamp}.json"
        report.write_text(
            json.dumps(
                {
                    "kind": "meta-traps",
                    "date": _dt.datetime.now().isoformat(timespec="seconds"),
                    "cases_file": str(path),
                    "system": SYSTEM,
                    "models": [{"provider": p, "model": m} for p, m in models],
                    "forms": {f: FORMS[f] for f in forms},
                    "tokenizer": tok.label,
                    "prompt_tokens": tokens,
                    "cases": [
                        {
                            "num": c.num,
                            "title": c.title,
                            "expected": c.expected,
                            "traps": c.traps,
                            "prompts": c.prompts,
                        }
                        for c in cases
                    ],
                    "results": [
                        asdict(r)
                        for r in sorted(
                            results,
                            key=lambda r: (
                                r.provider,
                                r.model,
                                r.case,
                                r.form,
                                r.trial,
                            ),
                        )
                    ],
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
        print(paint.dim(f"\n  Report with every prompt and raw reply: {report}"))
    print(paint.dim(f"  {time.perf_counter() - started:.0f} s"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
