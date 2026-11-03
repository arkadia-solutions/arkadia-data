"""make analyze: paired comparison of formats from an AI report."""

from arkadia.bench import ai_bench
from arkadia.bench.analyze import analyze, mcnemar


def test_mcnemar():
    assert mcnemar(0, 0) == 1.0
    assert mcnemar(2, 7) > 0.05
    assert mcnemar(0, 12) < 0.001


def test_analyze_lists_misses():
    def answers(system, user):
        # JSON always right (echo nothing useful), AK-DATA always wrong
        return ""

    report = ai_bench.run(
        ai_bench.Scripted(answers), formats=["json", "akcd"], random_sets=1
    )
    d = report.to_dict()
    # pretend JSON answered everything
    for t in d["trials"]:
        if t["format"] == "json":
            t["misses"] = []
    text = analyze(d, "json", "akcd", limit=3)
    assert "Paired with" in text and "worse" in text
    assert "Right in JSON" in text
