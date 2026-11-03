"""Metadata benchmark: variants decode equal, an oracle scores 100%, a blind model fails meta questions."""

import re

from arkadia.bench import annotated, meta_bench
from arkadia.bench.ai_bench import Scripted
from arkadia.bench.site import build


def _answers(user: str, know_meta: bool) -> str:
    ds = next(d for d in annotated.datasets() if d.questions[0].text in user)
    out = []
    for i, q in enumerate(ds.questions, 1):
        a = q.answer if (know_meta or not q.needs_meta) else "unknown"
        out.append(f"{i}. {', '.join(map(str, a)) if isinstance(a, list) else a}")
    return "\n".join(out)


def test_every_variant_decodes_to_the_same_data():
    for ds in annotated.datasets():
        v = annotated.variants(ds)
        assert set(v) == set(annotated.VARIANTS)
        assert "/*" in v["comments"] and "$" not in re.sub(
            r'"[^"]*"', "", v["comments"].split("<", 1)[1].split("*/")[0]
        )
        assert "#" in v["attributes"] or "$" in v["attributes"]
        assert annotated.variants(ds, compact=False)["full"].count("\n") > 5


def test_oracle_and_blind_model():
    oracle = meta_bench.run(Scripted(lambda s, u: _answers(u, True)))
    t = oracle.table()
    assert all(r["meta_accuracy"] == 1 and r["plain_accuracy"] == 1 for r in t.values())
    blind = meta_bench.run(Scripted(lambda s, u: _answers(u, False)))
    t = blind.table()
    assert t["plain"]["meta_accuracy"] == 0 and t["plain"]["plain_accuracy"] == 1


def test_dry_run_and_site_export():
    dry = meta_bench.run(None)
    t = dry.table()
    assert t["full"]["prompt_tokens"] > t["plain"]["prompt_tokens"]
    assert t["plain"]["meta_accuracy"] is None
    token = {
        "tokenizer": "o200k_base",
        "formats": {"json": "JSON"},
        "rows": [],
        "totals": {"json": 1},
        "savings_vs_json_pct": {},
        "wins": {},
    }
    site = build([token], [], None, "1", [dry.to_dict()])
    assert len(site["ai"]["meta"]["prompt_sizes"]["variants"]) == 6
    assert site["ai"]["meta"]["models"] == []
    real = meta_bench.run(Scripted(lambda s, u: _answers(u, True), model="m"))
    site = build([token], [], site, "1", [real.to_dict()])
    assert site["ai"]["meta"]["models"][0]["model"] == "m"
