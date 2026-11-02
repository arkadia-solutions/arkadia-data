"""
Lossless round-trip: JSON -> AK-Data -> JSON must return the same value.

Covers the cases that used to lose data: heterogeneous lists, records whose
keys differ from the header, lists mixing records and lists, nested lists of
records, empty objects and [any] element types.
"""

import random

import pytest

import arkadia.data as akd

CONFIGS = [
    {"compact": True},
    {"compact": False},
    {"compact": True, "escape_new_lines": True},
]

CASES = [
    {"items": [{"a": 1}, [1, 2]]},
    {"t": [{"i": {"tags": ["a"]}}, {"i": {"nums": [1]}}]},
    {"t": [{"i": {"pairs": [["a"]]}}, {"i": ["x", 1]}]},
    {"i": {}},
    [{}, {"a": 1}],
    {},
    [],
    [[{"a": 1}, {"a": 2}], [{"a": 3}]],
    [[], [None, 1]],
    [[], [{"a": 1}, {"a": 2}]],
    {"items": [{"a": 1, "b": 2}, {"a": 3}]},
    {"items": [{"a": 1}, {"a": "x"}, {"a": None}, {"a": [1]}]},
    [1, "a", True, None, 2.5, {"k": "v"}, [1]],
    {"x y": {"ł": "ząb", "v-1": "(x)"}},
    {"s": ['q"t', "a,b", "new\nline", "<any>", "{", "null", "true", "12"]},
    {"pairs": [["a", "b"], ["c", "d"]], "deep": [[[{"id": 1}]]]},
    {"": 1},
    {"a": {"": 1}, "t": [{"": 1}, {"": 2}]},
]

KEYS = ["a", "b", "c", "id", "name", "x y", "ł", "tags", "v-1"]
PRIMS = [
    None,
    True,
    False,
    0,
    1,
    -3,
    2.5,
    "",
    "s",
    "a,b",
    "(x)",
    "new\nline",
    'q"t',
    "<any>",
    "{",
    "null",
    "true",
    "12",
    "ząb",
    " pad ",
]


def _gen(rnd: random.Random, depth: int = 0):
    r = rnd.random()
    if depth > 3 or r < 0.35:
        return rnd.choice(PRIMS)
    if r < 0.65:
        return [_gen(rnd, depth + 1) for _ in range(rnd.randint(0, 4))]
    if r < 0.8:
        keys = rnd.sample(KEYS, rnd.randint(1, 3))
        return [
            {
                k: _gen(rnd, depth + 2)
                for k in (keys if rnd.random() < 0.8 else rnd.sample(KEYS, 2))
            }
            for _ in range(rnd.randint(1, 4))
        ]
    return {k: _gen(rnd, depth + 1) for k in rnd.sample(KEYS, rnd.randint(0, 4))}


def _roundtrip(value, config):
    text = akd.encode(value, config)
    result = akd.decode(text)
    assert not result.errors, (text, result.errors)
    assert result.node.dict() == value, text


@pytest.mark.parametrize("config", CONFIGS)
@pytest.mark.parametrize("value", CASES)
def test_known_cases(value, config):
    _roundtrip(value, config)


@pytest.mark.parametrize("seed", range(5))
def test_random_documents(seed):
    rnd = random.Random(seed)
    for _ in range(300):
        value = _gen(rnd)
        for config in CONFIGS:
            _roundtrip(value, config)
