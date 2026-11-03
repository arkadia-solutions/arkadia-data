"""Generated datasets, the harder question kinds and the AI benchmark plumbing."""

import json

from arkadia.bench import ai_bench
from arkadia.bench.formats import available_formats
from arkadia.bench.generate import SHAPES, generate


def test_generated_datasets_are_deterministic():
    a = [d.data for d in generate(10, seed=3)]
    b = [d.data for d in generate(10, seed=3)]
    c = [d.data for d in generate(10, seed=4)]
    assert a == b
    assert a != c
    names = [d.name for d in generate(len(SHAPES), seed=1)]
    assert {n.split("-", 2)[2] for n in names} == set(SHAPES)


def test_every_format_round_trips_the_generated_data():
    formats = available_formats(variants=True)
    for ds in generate(14, seed=11):
        for key in ("akd", "akcd", "akd-n", "akcd-n"):
            fmt = formats[key]
            assert fmt.decode(fmt.encode(ds.data)) == ds.data, (ds.name, key)


def test_questions_cover_many_kinds_and_answers_score():
    sets = generate(21, seed=5)
    kinds = set()
    for ds in sets:
        for q in ai_bench.make_questions(ds, 16):
            kinds.add(q.kind)
            answer = (
                ", ".join(map(str, q.answer))
                if isinstance(q.answer, list)
                else json.dumps(q.answer)
            )
            assert ai_bench.score(answer.strip('"'), q.answer), (q.text, q.answer)
    assert {
        "position",
        "count2",
        "filter",
        "optional",
        "inner-sum",
        "contains",
    } <= kinds


def _text(a):
    if isinstance(a, list):
        return ", ".join(map(str, a))
    return a if isinstance(a, str) else json.dumps(a)


EXPECTED = {}


def _perfect(system, user):
    lines = [
        q.split(". ", 1)[1] for q in user.split("Questions:\n", 1)[1].splitlines() if q
    ]
    answers = EXPECTED[tuple(lines)]
    return "\n".join(f"{i}. {a}" for i, a in enumerate(answers, 1))


def test_run_with_random_sets_and_repeats():
    for ds in ai_bench.benchmark_sets(None, random_sets=3, seed=2):
        qs = ai_bench.make_questions(ds, 16, 2)
        EXPECTED[tuple(q.text for q in qs)] = [_text(q.answer) for q in qs]
    report = ai_bench.run(
        ai_bench.Scripted(_perfect),
        formats=["json", "akcd-n"],
        random_sets=3,
        seed=2,
        repeats=2,
    )
    s = report.summary()
    assert report.source.endswith("+ 3 generated (seed 2)")
    assert s["akcd-n"]["accuracy"] == 1.0
    assert s["json"]["questions"] == 2 * sum(len(v) for v in report.questions.values())
    lo, hi = s["json"]["ci95"]
    assert 0.98 < lo < hi <= 1.0
    assert "95% CI" in ai_bench.to_markdown(report)


def test_wilson_interval():
    lo, hi = ai_bench.wilson(65, 81)
    assert 0.70 < lo < 0.71 and 0.87 < hi < 0.88


def test_openai_body_for_reasoning_models():
    old = ai_bench.OpenAICompatible("gpt-4o-mini", api_key="x")._body("s", "u", 100)
    assert old["temperature"] == 0 and old["max_tokens"] == 100
    new = ai_bench.OpenAICompatible("gpt-5.4-mini", api_key="x", reasoning="low")._body(
        "s", "u", 100
    )
    assert "temperature" not in new and "max_tokens" not in new
    assert new["max_completion_tokens"] > 100 and new["reasoning_effort"] == "low"
