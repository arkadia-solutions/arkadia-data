"""arkadia.data json-like API, tokenizer fallback and the token benchmark."""

import io

import pytest

import arkadia.data as akd
from arkadia.bench import bench
from arkadia.bench.datasets import bundled, load_dir
from arkadia.data import tokens


def test_dumps_loads_roundtrip():
    obj = {"users": [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Alan"}], "ok": True}
    text = akd.dumps(obj)
    assert "\n" not in text and akd.loads(text) == obj
    pretty = akd.dumps(obj, indent=2)
    assert "\n" in pretty and akd.loads(pretty) == obj
    assert akd.loads(akd.dumps(obj, types=False)) == obj
    buf = io.StringIO()
    akd.dump(obj, buf)
    buf.seek(0)
    assert akd.load(buf) == obj


def test_loads_strict_errors():
    with pytest.raises(akd.AKDataError):
        akd.loads("<a:number>(1")
    assert akd.loads_any('```json\n{"a": 1}\n```') == {"a": 1}
    assert akd.loads_any("<a:number>(1)") == {"a": 1}


def test_to_prompt_contains_hint_and_data():
    block = akd.to_prompt([{"a": 1}, {"a": 2}])
    assert akd.HINT in block and "<data>" in block and "(1)" in block


def test_tokenizer_never_raises():
    approx = tokens.get_tokenizer("approx")
    assert not approx.exact and approx.count('{"a": [1, 2, 3]}') > 0
    assert tokens.count_tokens("hello world") > 0


def test_bundled_datasets():
    names = {d.name for d in bundled()}
    assert {
        "employees",
        "orders",
        "tool-results",
        "rag-chunks",
        "logs",
        "config",
    } <= names


def test_benchmark_bundled_is_lossless_and_smaller():
    report = bench.run(
        repeats=0, formats=["json", "json-min", "akd", "akcd"], encoding="approx"
    )
    totals = report.totals()
    assert totals["akcd"] < totals["json-min"] < totals["json"]
    for row in report.rows:
        for key, cell in row.cells.items():
            assert cell.error is None and cell.lossless, (row.dataset, key)
    md = bench.to_markdown(report)
    assert "| employees |" in md


def test_benchmark_dir(tmp_path):
    (tmp_path / "a.json").write_text('{"x": [{"id": 1}, {"id": 2}]}')
    (tmp_path / "a.ak-data").write_text("<x:<[id:number]>>([(1),(2)])")
    report = bench.run(directory=str(tmp_path), repeats=0, encoding="approx")
    assert [r.dataset for r in report.rows] == ["a"]
    assert report.rows[0].reference_ok is True
    with pytest.raises(FileNotFoundError):
        load_dir(tmp_path / "missing")
