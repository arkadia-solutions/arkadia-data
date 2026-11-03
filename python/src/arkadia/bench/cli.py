"""
Benchmark runner for the repository (`make benchmark`), not part of `ak-data`.

    python -m arkadia.bench                  tokens → AI → HTML report in reports/
    python -m arkadia.bench --only-show      print every AI-benchmark prompt, run nothing

One run does three steps:
  1. token / speed / fidelity benchmark (JSON, YAML, TOON, AK-DATA) per tokenizer
  2. AI benchmark: a model answers questions about the data in every format
     (a dry run with prompt sizes only when no model is configured), then the
     metadata benchmark: the same annotated data with and without comments
     and tags (--no-meta skips it)
  3. HTML report with a summary (written by the model, or computed from the numbers)
"""

from __future__ import annotations

import argparse
import json
import pathlib

from arkadia.bench.colors import C

BAR = 22
FORMAT_COLORS = {
    "json": "\033[38;5;39m",
    "json-min": "\033[38;5;33m",
    "yaml": "\033[38;5;141m",
    "toon": "\033[38;5;208m",
    "akd": "\033[38;5;34m",
    "akcd": "\033[38;5;118m",
}


def _bar(value, maximum, width=BAR):
    if maximum <= 0:
        return " " * width
    filled = max(1, round(value / maximum * width)) if value else 0
    return "█" * filled + "░" * (width - filled)


def _print_details(report):
    keys = list(report.formats)
    for row in report.rows:
        ok = {k: c for k, c in row.cells.items() if c.error is None}
        if not ok:
            continue
        top = max(c.tokens for c in ok.values())
        best = min(c.tokens for c in ok.values())
        desc = f"  {C.DIM}{row.description}{C.RESET}" if row.description else ""
        print(f"{C.BOLD}{row.dataset}{C.RESET}{desc}")
        for k in keys:
            c = row.cells[k]
            color = FORMAT_COLORS.get(k, C.WHITE)
            if c.error:
                print(f"   {k:9} {C.RED}{c.error[:90]}{C.RESET}")
                continue
            mark = f"{C.GREEN}◀ fewest{C.RESET}" if c.tokens == best else ""
            lossy = "" if c.lossless in (True, None) else f"{C.RED} lossy{C.RESET}"
            timing = ""
            if c.encode_ms:
                dec = f" / {c.decode_ms:6.3f}" if c.decode_ms is not None else ""
                timing = f"{C.DIM}{c.encode_ms:6.3f}{dec} ms{C.RESET}"
            print(
                f"   {k:9} {color}{_bar(c.tokens, top)}{C.RESET} "
                f"{c.tokens:7,} tok  {timing}{lossy} {mark}"
            )
        if row.reference_ok is not None:
            state = (
                f"{C.GREEN}OK{C.RESET}"
                if row.reference_ok
                else f"{C.RED}errors{C.RESET}"
            )
            print(f"   {C.DIM}reference .ak-data decodes:{C.RESET} {state}")
        print()


def _print_summary(report):
    keys = list(report.formats)
    totals = report.totals()
    savings = report.savings()
    wins = report.wins()
    w = 11
    approx = "" if report.exact_tokens else " (approx.)"
    print(
        f"{C.BOLD}SUMMARY{C.RESET}  {C.DIM}{len(report.rows)} datasets · "
        f"{report.source} · tokens: {report.tokenizer}{approx}{C.RESET}"
    )
    print(f"{C.DIM}   {'dataset':16}" + "".join(f"{k:>{w}}" for k in keys) + C.RESET)
    for row in report.rows:
        ok = [c.tokens for c in row.cells.values() if c.error is None]
        best = min(ok) if ok else None
        line = f"   {row.dataset[:16]:16}"
        for k in keys:
            c = row.cells[k]
            if c.error:
                line += f"{C.RED}{'error':>{w}}{C.RESET}"
                continue
            txt = f"{c.tokens:,}" + ("" if c.lossless in (True, None) else "!")
            color = C.GREEN if c.tokens == best else ""
            line += f"{color}{txt:>{w}}{C.RESET}"
        print(line)
    print(f"   {'-' * (16 + w * len(keys))}")
    print(
        f"   {'TOTAL':16}"
        + "".join(f"{(f'{totals[k]:,}' if k in totals else '–'):>{w}}" for k in keys)
    )
    line = f"   {'vs JSON':16}"
    for k in keys:
        if k not in savings:
            line += f"{'–':>{w}}"
            continue
        s = savings[k]
        color = C.GREEN if s < 0 else (C.DIM if s == 0 else C.RED)
        line += f"{color}{f'{s:+.1f}%':>{w}}{C.RESET}"
    print(line)
    print(
        f"   {'fewest tokens':16}"
        + "".join(f"{f'{wins.get(k, 0)}x':>{w}}" for k in keys)
    )

    lossy = sorted(
        {k for r in report.rows for k, c in r.cells.items() if c.lossless is False}
    )
    if lossy:
        print(
            f"\n   {C.RED}!{C.RESET} decoding did not return the original data for: "
            f"{', '.join(lossy)}"
        )

    if "akcd" in totals:
        rivals = {k: v for k, v in totals.items() if k not in ("akcd", "akd")}
        if rivals:
            best = min(rivals, key=rivals.get)
            diff = (totals["akcd"] - rivals[best]) / rivals[best] * 100
            color = C.GREEN if diff < 0 else C.RED
            word = "fewer" if diff < 0 else "more"
            vs_json = savings.get("akcd")
            tail = f", {abs(vs_json):.1f}% fewer than JSON" if vs_json else ""
            print(
                f"\n{C.BOLD}RESULT:{C.RESET} AK-Data compact uses {color}"
                f"{abs(diff):.1f}% {word}{C.RESET} tokens than the best alternative "
                f"({report.formats[best]}){tail}."
            )


def _pct(v):
    return "–" if v is None else f"{v * 100:5.1f}%"


def _print_ai(report):
    s = report.summary()
    keys = [k for k in report.formats if k in s]
    total_q = sum(len(v) for v in report.questions.values())
    who = (
        "DRY RUN (no model called)"
        if report.dry_run
        else f"{report.provider} · {report.model}"
    )
    print(
        f"\n{C.BOLD}AI BENCHMARK{C.RESET}  {C.DIM}{who} · {len(report.questions)} datasets · {total_q} questions · hint {report.hint} · tokens {report.tokenizer}{C.RESET}"
    )
    head = f"   {'format':26}{'accuracy':>10}{'95% CI':>14}{'correct':>10}{'prompt tok':>12}{'data tok':>11}{'per 10k tok':>13}"
    if report.writes:
        head += f"{'writes ok':>11}"
    print(f"{C.DIM}{head}{C.RESET}")
    best_acc = max((s[k]["accuracy"] or 0) for k in keys) if keys else 0
    least_tok = min(s[k]["prompt_tokens"] for k in keys) if keys else 0
    for k in keys:
        r = s[k]
        acc_col = (
            C.GREEN if r["accuracy"] is not None and r["accuracy"] == best_acc else ""
        )
        tok_col = C.GREEN if r["prompt_tokens"] == least_tok else ""
        eff = (
            "–"
            if r["correct_per_10k_tokens"] is None
            else f"{r['correct_per_10k_tokens']:.1f}"
        )
        correct = "–" if report.dry_run else f"{r['correct']}/{r['questions']}"
        ci = (
            f"{r['ci95'][0] * 100:.0f}–{r['ci95'][1] * 100:.0f}%"
            if r.get("ci95")
            else "–"
        )
        line = (
            f"   {report.formats[k]:26}{acc_col}{_pct(r['accuracy']):>10}{C.RESET}{ci:>14}{correct:>10}"
            f"{tok_col}{r['prompt_tokens']:>12,}{C.RESET}{r['data_tokens']:>11,}{eff:>13}"
        )
        if report.writes:
            line += f"{_pct(r['write_valid']):>11}"
        print(line)
    errors = [t for t in report.trials if t.error]
    if errors:
        print(
            f"\n   {C.RED}{len(errors)} request(s) failed{C.RESET}, first: {errors[0].error[:160]}"
        )
    if not report.dry_run and keys:
        kinds = sorted({kind for k in keys for kind in s[k]["by_kind"]})
        print(
            f"\n{C.DIM}   {'by question type':18}"
            + "".join(f"{k:>10}" for k in keys)
            + C.RESET
        )
        for kind in kinds:
            print(
                f"   {kind:18}"
                + "".join(f"{_pct(s[k]['by_kind'].get(kind)):>10}" for k in keys)
            )
    if "akcd" in s and "json" in s:
        a, j = s["akcd"], s["json"]
        saved = (j["prompt_tokens"] - a["prompt_tokens"]) / j["prompt_tokens"] * 100
        msg = f"AK-Data prompts are {saved:.1f}% smaller than JSON"
        if (
            not report.dry_run
            and a["accuracy"] is not None
            and j["accuracy"] is not None
        ):
            diff = (a["accuracy"] - j["accuracy"]) * 100
            msg += f", accuracy {diff:+.1f} pts vs JSON"
        print(f"\n{C.BOLD}RESULT:{C.RESET} {msg}.")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def _split(value):
    return [v.strip() for v in value.split(",") if v.strip()] if value else None


def _slug(text):
    return (
        "".join(ch if ch.isalnum() or ch in "._" else "-" for ch in text) or "default"
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m arkadia.bench",
        description="AK-DATA benchmark: tokens, AI comprehension and an HTML report.",
    )
    p.add_argument(
        "--only-show",
        action="store_true",
        help="Print every AI-benchmark prompt and exit (no model calls, no files)",
    )
    p.add_argument(
        "-d",
        "--dir",
        default=None,
        help="Folder with *.json files (default: bundled datasets)",
    )
    p.add_argument(
        "-f",
        "--formats",
        default=None,
        help="Comma-separated formats, e.g. json,toon,akcd",
    )
    p.add_argument(
        "-o", "--out", default="reports", help="Output folder (default: reports)"
    )
    p.add_argument(
        "-t",
        "--tokenizers",
        default="o200k_base,cl100k_base",
        help="Comma-separated tokenizers",
    )
    p.add_argument(
        "-r",
        "--repeats",
        type=int,
        default=20,
        help="Timing repeats (first tokenizer only)",
    )
    p.add_argument(
        "-p",
        "--provider",
        default="auto",
        help="auto, openai, anthropic, ollama, openrouter",
    )
    p.add_argument(
        "-m",
        "--model",
        default=None,
        help="Model id; comma-separated for several models",
    )
    p.add_argument("--base-url", default=None, help="OpenAI-compatible endpoint")
    network = p.add_mutually_exclusive_group()
    network.add_argument(
        "--allow-network",
        action="store_true",
        help="Explicitly allow sending datasets and reports to the selected model provider",
    )
    network.add_argument(
        "--offline",
        action="store_true",
        help="Never load provider credentials or make model requests (default)",
    )
    p.add_argument(
        "-n", "--questions", type=int, default=16, help="Questions per dataset"
    )
    p.add_argument(
        "--random",
        type=int,
        default=0,
        metavar="N",
        help="AI benchmark: add N randomly generated datasets (more questions)",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=7,
        help="Seed of the generated datasets and questions",
    )
    p.add_argument(
        "--trials",
        type=int,
        default=1,
        help="AI benchmark: send every prompt this many times",
    )
    p.add_argument(
        "--reasoning",
        default=None,
        choices=["none", "minimal", "low", "medium", "high"],
        help="reasoning_effort for GPT-5 / o-series models (default: the model's)",
    )
    p.add_argument(
        "--hint",
        choices=["auto", "all", "none"],
        default="all",
        help="Format definition in prompts: all (AK-Data and TOON), auto (AK-Data), none",
    )
    p.add_argument(
        "--write", action="store_true", help="Also ask the model to write each format"
    )
    p.add_argument("--parallel", type=int, default=4, help="Parallel model requests")
    p.add_argument(
        "--no-meta",
        action="store_true",
        help="Skip the metadata benchmark (comments and tags vs none)",
    )
    p.add_argument(
        "--summary",
        choices=["auto", "ai", "numbers"],
        default="auto",
        help="Who writes the report summary",
    )
    p.add_argument("--lang", default="en", help="Summary language")
    p.add_argument("--title", default="AK-DATA benchmark report", help="Report title")
    p.add_argument(
        "--site",
        action="append",
        default=[],
        metavar="FILE",
        help="Also write the numbers for the website to FILE (repeatable; bundled datasets only)",
    )
    return p


def show_prompts(args) -> int:
    from arkadia.bench.ai_bench import list_prompts
    from arkadia.bench.meta_bench import list_prompts as meta_prompts

    prompts = list_prompts(
        directory=args.dir,
        formats=_split(args.formats),
        questions=args.questions,
        hint=args.hint,
        write=args.write,
        random_sets=args.random,
        seed=args.seed,
    )
    if not args.no_meta:
        prompts += meta_prompts()
    rule = "=" * 78
    for i, item in enumerate(prompts, 1):
        print(rule)
        print(
            f"PROMPT {i}/{len(prompts)} · dataset: {item['dataset']} · format: {item['format']} · {item['kind']}"
        )
        print(rule)
        print(f"[system]\n{item['system']}\n")
        print(f"[user]\n{item['user']}")
        if item["answers"] is not None:
            print("\n[expected answers]")
            for n, answer in enumerate(item["answers"], 1):
                print(f"{n}. {json.dumps(answer, ensure_ascii=False)}")
        print()
    print(f"{len(prompts)} prompts.")
    return 0


def run_tokens(args, out: pathlib.Path, tag: str) -> list:
    from arkadia.bench.bench import run as run_bench
    from arkadia.bench.bench import to_markdown
    from arkadia.bench.formats import missing_formats
    from arkadia.data.tokens import tokenizer_status

    written = []
    missing = missing_formats()
    if missing and not args.formats:
        print(f"{C.DIM}Not compared (library missing): {', '.join(missing)}{C.RESET}")
    for i, tokenizer in enumerate(_split(args.tokenizers) or ["o200k_base"]):
        warning = tokenizer_status(tokenizer)
        if warning:
            print(f"{C.YELLOW}Note:{C.RESET} {warning}")
        report = run_bench(
            directory=args.dir,
            formats=_split(args.formats),
            encoding=tokenizer,
            repeats=max(0, args.repeats) if i == 0 else 0,
        )
        print()
        if i == 0:
            _print_details(report)
        _print_summary(report)
        base = out / f"benchmark-{tag}-{tokenizer}"
        (base.parent / (base.name + ".json")).write_text(
            json.dumps(report.to_dict(), indent=2), encoding="utf-8"
        )
        (base.parent / (base.name + ".md")).write_text(
            to_markdown(report), encoding="utf-8"
        )
        print(f"\n{C.DIM}Written {base}.json / .md{C.RESET}")
        written.append(base.parent / (base.name + ".json"))
    return written


def network_provider(args, model=None):
    """Only an explicit flag may cross the local-data/network boundary."""
    if getattr(args, "offline", False) or not getattr(args, "allow_network", False):
        return None
    from urllib.parse import urlsplit

    from arkadia.bench.ai_bench import provider_from_env

    provider = provider_from_env(
        args.provider, model, args.base_url, reasoning=getattr(args, "reasoning", None)
    )
    if provider is not None:
        address = urlsplit(getattr(provider, "base_url", ""))
        host = address.hostname or "configured provider"
        print(
            f"NETWORK ENABLED: provider={args.provider}, host={host}, model={provider.model}, data={args.dir or 'bundled synthetic datasets'}"
        )
        print(
            "Dataset contents and report inputs may be sent to this provider. Reports can contain prompt/answer excerpts."
        )
    return provider


def run_ai(args, out: pathlib.Path, tag: str) -> list:
    from arkadia.bench.ai_bench import run as run_ai_bench
    from arkadia.bench.ai_bench import to_markdown

    written = []
    models = _split(args.model) or [None]
    for model in models:
        provider = network_provider(args, model)
        if provider is None:
            print(
                f"\n{C.YELLOW}No model configured{C.RESET} (set OPENAI_API_KEY, ANTHROPIC_API_KEY, "
                "or PROVIDER=ollama MODEL=<name>): AI dry run, prompt sizes only."
            )

        def progress(msg):
            print(f"   {C.DIM}{msg}{C.RESET}")

        report = run_ai_bench(
            provider,
            directory=args.dir,
            formats=_split(args.formats),
            questions=args.questions,
            hint=args.hint,
            write=args.write,
            encoding=(_split(args.tokenizers) or ["o200k_base"])[0],
            parallel=args.parallel,
            progress=progress if provider else None,
            random_sets=args.random,
            seed=args.seed,
            repeats=args.trials,
        )
        _print_ai(report)
        name = _slug(provider.model) if provider else "dry-run"
        base = out / f"ai-{tag}-{name}"
        (base.parent / (base.name + ".json")).write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (base.parent / (base.name + ".md")).write_text(
            to_markdown(report), encoding="utf-8"
        )
        print(f"\n{C.DIM}Written {base}.json / .md{C.RESET}")
        written.append(base.parent / (base.name + ".json"))
        if provider is None:
            break
    return written


def _print_meta(report):
    rows = report.table()
    who = (
        "DRY RUN (no model called)"
        if report.dry_run
        else f"{report.provider} · {report.model}"
    )
    n_meta = sum(sum(q["needs_meta"] for q in qs) for qs in report.questions.values())
    n_all = sum(len(qs) for qs in report.questions.values())
    print(
        f"\n{C.BOLD}METADATA BENCHMARK{C.RESET}  {C.DIM}{who} · {len(report.questions)} datasets · "
        f"{n_all} questions ({n_meta} need the metadata){C.RESET}"
    )
    print(
        f"{C.DIM}   {'variant':34}{'prompt tok':>11}{'meta Q':>9}{'plain Q':>9}{C.RESET}"
    )
    base = rows.get("plain", {}).get("prompt_tokens") or 1
    for r in rows.values():
        acc = lambda v: "–" if v is None else f"{v * 100:.0f}%"  # noqa: E731
        extra = (r["prompt_tokens"] - base) / base * 100
        print(
            f"   {r['label']:34}{r['prompt_tokens']:>11,}{acc(r['meta_accuracy']):>9}{acc(r['plain_accuracy']):>9}"
            f"  {C.DIM}{extra:+.0f}% vs no metadata{C.RESET}"
        )


def run_meta(args, out: pathlib.Path, tag: str) -> list:
    from arkadia.bench.meta_bench import run as run_meta_bench
    from arkadia.bench.meta_bench import to_markdown

    if args.no_meta:
        return []
    written = []
    for model in _split(args.model) or [None]:
        provider = network_provider(args, model)

        def progress(msg):
            print(f"   {C.DIM}{msg}{C.RESET}")

        report = run_meta_bench(
            provider,
            encoding=(_split(args.tokenizers) or ["o200k_base"])[0],
            parallel=args.parallel,
            progress=progress if provider else None,
        )
        _print_meta(report)
        name = _slug(provider.model) if provider else "dry-run"
        base = out / f"meta-{name}"
        (base.parent / (base.name + ".json")).write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (base.parent / (base.name + ".md")).write_text(
            to_markdown(report), encoding="utf-8"
        )
        print(f"\n{C.DIM}Written {base}.json / .md{C.RESET}")
        written.append(base.parent / (base.name + ".json"))
        if provider is None:
            break
    return written


def run_site(args, token_paths: list, ai_paths: list, meta_paths: list = ()) -> None:
    from arkadia.bench.site import export
    from arkadia.data import __version__

    if not args.site:
        return
    if args.dir or args.formats:
        print(
            f"\n{C.DIM}Website numbers not updated: they come from the bundled datasets "
            f"with every format (run without DIR / --formats).{C.RESET}"
        )
        return
    paths = export(
        token_paths,
        ai_paths,
        [pathlib.Path(p) for p in args.site],
        __version__,
        meta_paths=list(meta_paths),
    )
    for p in paths:
        print(f"{C.GREEN}Website:{C.RESET} {p}")


def run_report(args, out: pathlib.Path) -> None:
    from arkadia.bench.report import build, load_inputs

    found = load_inputs([out])
    provider = None
    if args.summary != "numbers":
        provider = network_provider(args, (_split(args.model) or [None])[0])
        if provider is None and args.summary == "ai":
            raise ValueError(
                "--summary ai needs a model (OPENAI_API_KEY, ANTHROPIC_API_KEY or PROVIDER=ollama MODEL=…)"
            )
    path, source = build([out], out / "report.html", provider, args.lang, args.title)
    print(
        f"\n{C.GREEN}Report:{C.RESET} {path}  {C.DIM}({len(found.benchmarks)} token benchmark(s), "
        f"{len(found.ai)} AI benchmark(s)) · {source}{C.RESET}"
    )


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if not args.allow_network or args.offline:
            print(
                "OFFLINE: no model credentials are loaded and no model requests are made. Use --allow-network to opt in."
            )
        if args.only_show:
            return show_prompts(args)
        out = pathlib.Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        tag = pathlib.Path(args.dir).resolve().name if args.dir else "bundled"
        print(f"{C.BOLD}[1/3] Token benchmark{C.RESET}")
        token_paths = run_tokens(args, out, tag)
        print(f"\n{C.BOLD}[2/3] AI benchmark{C.RESET}")
        ai_paths = run_ai(args, out, tag)
        meta_paths = run_meta(args, out, tag)
        print(f"\n{C.BOLD}[3/3] HTML report{C.RESET}")
        run_report(args, out)
        run_site(args, token_paths, ai_paths, meta_paths)
    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}Cancelled.{C.RESET}")
        return 130
    except (FileNotFoundError, ValueError) as exc:
        print(f"{C.RED}Error:{C.RESET} {exc}")
        return 2
    return 0
