"""Benchmark report: HTML from token + AI benchmark JSON, with summaries."""

import json

from arkadia.bench import ai_bench, bench, report
from arkadia.bench.datasets import bundled


def _answer(q):
    return ", ".join(map(str, q.answer)) if isinstance(q.answer, list) else q.answer


def _write_inputs(tmp_path):
    b = bench.run(repeats=0, formats=["json", "json-min", "akcd"], encoding="approx")
    (tmp_path / "benchmark.json").write_text(json.dumps(b.to_dict()))
    ds = [d for d in bundled() if d.name in ("employees", "config")]
    qmap = {d.name: ai_bench.make_questions(d, 6) for d in ds}

    def perfect(system, user):
        for qs in qmap.values():
            if qs[0].text in user:
                return "\n".join(f"{i}. {_answer(q)}" for i, q in enumerate(qs, 1))
        return ""

    kw = {"datasets": ds, "questions": 6, "formats": ["json", "akcd"]}
    a = ai_bench.run(ai_bench.Scripted(perfect, "oracle"), **kw)
    (tmp_path / "ai-oracle.json").write_text(json.dumps(a.to_dict()))
    dry = ai_bench.run(None, **kw)
    (tmp_path / "ai-dry.json").write_text(json.dumps(dry.to_dict()))
    (tmp_path / "notes.json").write_text('{"unrelated": true}')


def test_load_and_facts(tmp_path):
    _write_inputs(tmp_path)
    inputs = report.load_inputs([tmp_path])
    assert len(inputs.benchmarks) == 1 and len(inputs.ai) == 2
    assert not inputs.ai[0][1]["dry_run"]  # measured runs first
    f = report.facts(inputs)
    tb = f["token_benchmarks"][0]
    assert tb["totals"]["akcd"] < tb["totals"]["json"]
    assert f["ai_benchmarks"][0]["formats"]["akcd"]["accuracy_pct"] == 100.0


def test_auto_summary_languages(tmp_path):
    _write_inputs(tmp_path)
    f = report.facts(report.load_inputs([tmp_path]))
    en = report.auto_summary(f, "en")
    pl = report.auto_summary(f, "pl")
    assert "fewer than JSON" in en and "Recommendation" in en
    assert "mniej niż JSON" in pl and "Rekomendacja" in pl


def test_build_html_with_model_summary(tmp_path):
    _write_inputs(tmp_path)
    seen = {}

    def writer(system, user):
        seen["user"] = user
        return "**Headline.**\n\n- one\n- two <script>\n\nDone."

    provider = ai_bench.Scripted(writer, "w")
    out, source = report.build([tmp_path], tmp_path / "out" / "report.html", provider)
    page = out.read_text()
    assert "Summary written by scripted" in source
    assert "<b>Headline.</b>" in page and "<li>two &lt;script&gt;</li>" in page
    assert "<results>" in seen["user"]  # facts go to the model in AK-Data
    assert "AI comprehension" in page and "100.0%" in page
    summary = (tmp_path / "out" / "report.summary.md").read_text()
    assert summary.startswith("**Headline.**")


def test_build_falls_back_when_model_fails(tmp_path):
    _write_inputs(tmp_path)

    def broken(system, user):
        raise RuntimeError("boom")

    out, source = report.build(
        [tmp_path], tmp_path / "r.html", ai_bench.Scripted(broken)
    )
    assert "model call failed" in source and "fewer than JSON" in out.read_text()
