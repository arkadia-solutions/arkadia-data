"""Website numbers exported by `make benchmark` (arkadia.bench.site)."""

import json

from arkadia.bench import site


def _cell(t):
    return {
        "tokens": t,
        "chars": t * 3,
        "encode_ms": 0.1,
        "decode_ms": 0.2,
        "lossless": True,
        "error": None,
    }


def _token_report(tokenizer="o200k_base"):
    cell = _cell
    return {
        "tokenizer": tokenizer,
        "exact_tokens": True,
        "source": "bundled datasets",
        "formats": {
            "json": "JSON (indent 2)",
            "toon": "TOON",
            "akcd": "AK-Data compact",
        },
        "rows": [
            {
                "dataset": "a",
                "description": "d",
                "cells": {"json": cell(100), "toon": cell(60), "akcd": cell(50)},
            }
        ],
        "totals": {"json": 100, "toon": 60, "akcd": 50},
        "savings_vs_json_pct": {"json": 0.0, "toon": -40.0, "akcd": -50.0},
        "wins": {"json": 0, "toon": 0, "akcd": 1},
    }


def _ai_report(model, dry_run, accuracy):
    return {
        "provider": "openai" if model else "dry-run",
        "model": model,
        "tokenizer": "o200k_base",
        "hint": "auto",
        "dry_run": dry_run,
        "formats": {"json": "JSON (indent 2)", "akcd": "AK-Data compact"},
        "trials": [{"dataset": "a"}],
        "questions": {"a": [{}, {}]},
        "summary": {
            k: {
                "accuracy": accuracy,
                "correct": 1,
                "questions": 2,
                "prompt_tokens": t,
                "data_tokens": t - 10,
                "correct_per_10k_tokens": None,
                "by_kind": {"lookup": accuracy} if accuracy else {},
                "write_valid": None,
            }
            for k, t in (("json", 120), ("akcd", 70))
        },
    }


def test_headline_and_tables():
    data = site.build(
        [_token_report(), _token_report("cl100k_base")],
        [_ai_report("", True, None)],
        version="9.9",
    )
    assert data["headline"]["akcd_vs_json_pct"] == -50.0
    assert data["headline"]["akcd_vs_toon_pct"] == -16.7
    assert data["headline"]["lossless"] is True
    assert set(data["tokens"]) == {"o200k_base", "cl100k_base"}
    assert data["tokens"]["o200k_base"]["datasets"][0]["tokens"]["akcd"] == 50
    assert data["ai"]["prompt_sizes"]["questions"] == 2
    assert data["ai"]["models"] == []


def test_models_are_kept_across_runs(tmp_path):
    tok = tmp_path / "t.json"
    tok.write_text(json.dumps(_token_report()))
    with_model = tmp_path / "m.json"
    with_model.write_text(json.dumps(_ai_report("gpt-x", False, 0.5)))
    dry = tmp_path / "d.json"
    dry.write_text(json.dumps(_ai_report("", True, None)))
    out = tmp_path / "site" / "benchmark.json"
    site.export([tok], [with_model], [out])
    site.export([tok], [dry], [out])
    data = json.loads(out.read_text())
    assert [m["model"] for m in data["ai"]["models"]] == ["gpt-x"]
    assert data["ai"]["models"][0]["formats"][1]["accuracy"] == 0.5
