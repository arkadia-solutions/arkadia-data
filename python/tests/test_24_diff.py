"""diff / merge / apply / history — the same results as the Rust crate."""

import json
import random
from pathlib import Path

import pytest

from arkadia.data import diff as d
from arkadia.data import loads

CASES = json.loads((Path(__file__).parent / "fixtures/diff.json").read_text())["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_shared_fixtures(case):
    a, b = case["a"], case["b"]
    changes = d.diff(a, b)
    assert d.changes_json(changes) == case["changes"]
    assert d.merge(a, b) == case["merged"]
    assert d.apply(a, changes) == b
    assert d.apply(b, d.reverse(changes)) == a
    s = d.ChangeSet.new(
        changes,
        title="t",
        author="Ada",
        date="2026-11-01T10:00:00Z",
        parent="0123456789",
    )
    assert s.id == case["id"]
    assert d.with_history(b, [s]) == case["document"]
    # The history is metadata: the data decodes unchanged, the history reads back.
    assert loads(case["document"]) == b
    assert d.history(case["document"]) == [s]


def test_conflicts():
    changes = d.diff({"a": 1}, {"a": 2})
    with pytest.raises(d.ConflictError) as e:
        d.apply({"a": 5}, changes)
    assert "expected 1, found 5" in e.value.conflicts[0].reason
    assert d.apply({"a": 5}, changes, force=True) == {"a": 2}


def test_paths():
    assert d.parse_path('users[id=2].tags[1]["a b"][name="x]"]') == [
        ("key", "users"),
        ("match", "id", 2),
        ("key", "tags"),
        ("index", 1),
        ("key", "a b"),
        ("match", "name", "x]"),
    ]
    assert d.parse_path("$") == []
    with pytest.raises(ValueError):
        d.parse_path("a..b")


def test_commit_records_history():
    text = d.commit(
        '{"n": 1}', {"n": 2}, title="Bump", author="Ada", date="2026-11-01T10:00:00Z"
    )
    text = d.commit(text, {"n": 3}, title="Bump again", date="2026-11-01T11:00:00Z")
    assert loads(text) == {"n": 3}
    log = d.history(text)
    assert [s.title for s in log] == ["Bump", "Bump again"]
    assert log[1].changes[0].old == 2
    assert d.commit(text, {"n": 3}) == text  # nothing changed


def test_fuzz_round_trip():
    rnd = random.Random(7)

    def gen(depth=0):
        k = rnd.randrange(4 if depth > 2 else 7)
        if k == 0:
            return rnd.randrange(5)
        if k == 1:
            return rnd.choice("abc")
        if k == 2:
            return rnd.random() < 0.5
        if k == 3:
            return None
        if k == 4:
            return [gen(depth + 1) for _ in range(rnd.randrange(4))]
        if k == 5:
            ids = rnd.sample(range(6), rnd.randrange(5))
            return [{"id": i, "v": gen(depth + 1)} for i in ids]
        return {
            rnd.choice(["x", "y", "z", "w w"]): gen(depth + 1)
            for _ in range(rnd.randrange(4))
        }

    for _ in range(2000):
        a, b = gen(), gen()
        changes = d.diff(a, b)
        assert d.apply(a, changes) == b
        assert d.apply(b, d.reverse(changes)) == a
