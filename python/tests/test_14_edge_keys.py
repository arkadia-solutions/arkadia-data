"""Keys a header cannot spell, empty keys and duplicates still round-trip."""

import pytest

import arkadia.data as akd

CASES = [
    {"`q`": 1},
    [{"`q`": 1}, {"`q`": 2}],
    {"": [], "0": None},
    [{"": [], "0": None}, {"": 1}, {"": 2}],
    {"": 1, "0": 2},
    {"a\n": 1, "x y": [{"`": True}]},
    [],
    {"rows": []},
]


@pytest.mark.parametrize("data", CASES)
def test_round_trip(data):
    assert akd.loads(akd.dumps(data)) == data
    assert akd.loads(akd.dumps(data, indent=2)) == data


def test_backtick_key_is_written_by_name():
    assert akd.dumps({"`q`": 1}) == '{"`q`":1}'
    assert (
        akd.dumps({"id": 1, "name": "x"}, indent=2)
        == '< id:number, name:string >\n(1, "x")'
    )
    assert akd.dumps([], indent=2) == "<[any]>\n[\n]"
