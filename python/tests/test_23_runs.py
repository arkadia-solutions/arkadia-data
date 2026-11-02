"""Every test of an AI run: recorded prompts and replies, and older reports."""

import json

from arkadia.bench import ai_bench
from arkadia.bench.runs import build, export_run


def _echo(system, user):
    n = len(user.split("Questions:\n", 1)[1].splitlines())
    return "\n".join(f"{i}. 1" for i in range(1, n + 1))


def test_run_records_prompts_and_replies(tmp_path):
    report = ai_bench.run(
        ai_bench.Scripted(_echo), formats=["json", "akcd"], random_sets=2, seed=3
    )
    d = report.to_dict()
    t = d["trials"][0]
    assert t["prompt"].startswith("<data>") or "AK-Data" in t["prompt"]
    assert t["reply"].startswith("1. 1") and len(t["ok"]) == t["questions"]
    slug = export_run(d, tmp_path)
    index = json.loads((tmp_path / slug / "index.json").read_text())
    assert index["prompts"] == "recorded"
    name = index["datasets"][0]["name"]
    detail = json.loads((tmp_path / slug / f"{name}.json").read_text())
    assert detail["akcd"]["prompt"] and detail["akcd"]["reply"]
    assert len(index["datasets"][0]["results"]["json"]) == len(
        index["datasets"][0]["questions"]
    )


def test_older_reports_get_their_prompts_rebuilt():
    report = ai_bench.run(
        ai_bench.Scripted(_echo), formats=["toon", "akcd-n"], random_sets=1, seed=4
    )
    d = report.to_dict()
    for t in d["trials"]:  # what reports looked like before prompts were recorded
        for k in ("prompt", "reply", "answers", "ok"):
            t.pop(k)
    index, details = build(d)
    assert index["prompts"] == "rebuilt"
    assert all(
        v["prompt"] for ds in details.values() for k, v in ds.items() if k != "__data"
    )


def test_every_question_has_its_code():
    from arkadia.bench.runs import question_code

    for ds in ai_bench.benchmark_sets(None, random_sets=7, seed=9):
        for q in ai_bench.make_questions(ds, 16, 9):
            assert question_code(q.text), q.text
    assert (
        question_code('How many items in `rows` have `status` equal to "paid"?')
        == 'data["rows"].filter((r) => r["status"] === "paid").length'
    )
