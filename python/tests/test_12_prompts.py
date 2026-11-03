"""Copy-paste prompts and the bundled examples (with and without metadata)."""

import arkadia.data as akd
from arkadia.bench import prompts


def test_examples_load_and_roundtrip():
    exs = prompts.load_examples()
    assert [e.id for e in exs] == list(range(1, len(exs) + 1))
    assert len(exs) >= 50
    for e in exs:
        assert akd.loads(akd.dumps(e.data)) == e.data
        assert e.expected is not None and e.answer[1]


def test_prompt_in_every_format():
    ex = prompts.get_example("2")
    for fmt, marker in (
        ("json", '"orders"'),
        ("toon", "orders[15]:"),
        ("ak-data", "orders:<"),
        ("ak-data-compact", "<orders:<[id:string"),
    ):
        text = ex.prompt(fmt)
        assert marker in text and ex.question in text and "<data>" in text
    assert "AK-DATA (Arkadia Data Format)" in ex.prompt("akcd")
    assert "TOON (Token-Oriented" in ex.prompt("toon")
    assert "Answer in AK-DATA only" in ex.prompt("akcd")
    assert '"result": [{' in ex.prompt("json")
    assert "AK-DATA (Arkadia" not in ex.prompt("akcd", definition=False)


def test_normalize_format():
    assert prompts.normalize_format("AK-DATA COMPACT") == "akcd"
    assert prompts.normalize_format("ak_data") == "akd"
    try:
        prompts.normalize_format("xml")
        raise AssertionError
    except ValueError:
        pass


def test_expected_answers_are_computed():
    ex = prompts.get_example("employees-salaries")
    top = ex.expected
    assert (
        len(top) == 3
        and top[0]["avg_salary"] >= top[1]["avg_salary"] >= top[2]["avg_salary"]
    )


def test_metadata_toggles():
    from arkadia.bench.catalog import variant_text

    ex = prompts.get_example("invoices-overdue")
    assert "metadata" in ex.tags and "needs metadata" in ex.tags
    plain = ex.prompt("akcd")
    both = ex.prompt("akcd", comments=True, attributes=True)
    only_c = ex.prompt("akcd", comments=True)
    only_a = ex.prompt("akcd", attributes=True)
    assert "$unit" not in plain and "/*" not in plain.split("<data>")[1]
    assert "$unit" in both and "/* gross amount" in both
    assert "/* gross amount" in only_c and "$unit" not in only_c
    assert "$unit" in only_a and "/* gross amount" not in only_a
    for c in (False, True):
        for a in (False, True):
            assert akd.loads(variant_text(ex.akd_meta, c, a)) == ex.data
    j = ex.prompt("json", comments=True, attributes=True)
    assert "Notes about the data:" in j and "Attributes of the data:" in j
    assert "Notes about" not in ex.prompt("json")
    plain_ex = prompts.get_example("orders-revenue")
    assert plain_ex.akd_meta is None
    assert plain_ex.prompt("akcd", comments=True) == plain_ex.prompt("akcd")
