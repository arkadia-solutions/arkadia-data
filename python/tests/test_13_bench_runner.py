"""The repository benchmark runner (`make benchmark` → python -m arkadia.bench)."""

import json

import pytest

from arkadia.bench.cli import main

KEYS = ("OPENAI_API_KEY", "OPENAI_BASE_URL", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY")


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(
        "arkadia.bench.ai_bench.provider_from_env", lambda *a, **k: None
    )
    d = tmp_path / "data"
    d.mkdir()
    rows = [
        {"id": i, "name": f"user{i}", "team": "ab"[i % 2], "score": i * 3}
        for i in range(8)
    ]
    (d / "users.json").write_text(json.dumps({"users": rows}))
    return d


def test_only_show_prints_prompts_and_writes_nothing(data_dir, tmp_path, capsys):
    out = tmp_path / "reports"
    assert (
        main(
            [
                "--only-show",
                "--dir",
                str(data_dir),
                "--out",
                str(out),
                "-f",
                "json,akcd",
            ]
        )
        == 0
    )
    text = capsys.readouterr().out
    assert "PROMPT 1/2" in text and "format: akcd" in text
    assert "[system]" in text and "Questions:" in text and "[expected answers]" in text
    assert not out.exists()


def test_full_run_writes_reports_and_html(data_dir, tmp_path):
    out = tmp_path / "reports"
    argv = [
        "--dir",
        str(data_dir),
        "--out",
        str(out),
        "-r",
        "0",
        "-t",
        "o200k_base",
        "-n",
        "4",
    ]
    assert main(argv + ["--summary", "numbers"]) == 0
    names = sorted(p.name for p in out.iterdir())
    assert "benchmark-data-o200k_base.json" in names
    assert "ai-data-dry-run.json" in names
    assert "report.html" in names
