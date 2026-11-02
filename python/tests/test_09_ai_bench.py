"""AI benchmark: question generation, scoring and providers (no network)."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from arkadia.bench import ai_bench
from arkadia.bench.datasets import Dataset, bundled


def _answers_for(questions):
    def fmt(v):
        return (
            ", ".join(map(str, v))
            if isinstance(v, list)
            else json.dumps(v)
            if isinstance(v, str)
            else str(v)
        )

    return "\n".join(f"{i}. {fmt(q.answer)}" for i, q in enumerate(questions, 1))


def test_questions_are_deterministic_and_answerable():
    for ds in bundled():
        a = ai_bench.make_questions(ds, 12)
        b = ai_bench.make_questions(ds, 12)
        assert [q.text for q in a] == [q.text for q in b]
        assert a, ds.name
        assert all(q.dataset == ds.name for q in a)


def test_questions_cover_kinds():
    kinds = {q.kind for ds in bundled() for q in ai_bench.make_questions(ds, 12)}
    assert {
        "lookup",
        "count",
        "length",
        "fields",
        "extreme",
        "nested",
        "value",
    } <= kinds


def test_score_normalizes_answers():
    s = ai_bench.score
    assert s('"Ada Lovelace".', "Ada Lovelace")
    assert s("ada lovelace", "Ada Lovelace")
    assert s("42", 42) and s("42.0", 42) and s("There are 42 items", 42)
    assert s("1,234", 1234)
    assert s("true", True) and s("Yes", True) and not s("false", True)
    assert s("null", None) and s("None", None)
    assert s("b, a", ["a", "b"]) and not s("a", ["a", "b"])
    assert not s(None, 1) and not s("7", 8)


def test_parse_answers():
    text = "1. foo\n2) 12\nnoise\n3: bar\n3. ignored duplicate"
    assert ai_bench.parse_answers(text, 4) == ["foo", "12", "bar", None]


def test_perfect_and_wrong_providers():
    ds = [d for d in bundled() if d.name in ("employees", "orders", "config")]
    qmap = {d.name: ai_bench.make_questions(d, 8) for d in ds}

    def perfect(system, user):
        for name, qs in qmap.items():
            if qs[0].text in user:
                return _answers_for(qs)
        return ""

    report = ai_bench.run(ai_bench.Scripted(perfect), datasets=ds, questions=8)
    summary = report.summary()
    assert summary and all(r["accuracy"] == 1.0 for r in summary.values())
    assert summary["akcd"]["prompt_tokens"] < summary["json"]["prompt_tokens"]

    wrong = ai_bench.run(
        ai_bench.Scripted(lambda s, u: "1. nope"), datasets=ds, questions=8
    )
    assert all(r["accuracy"] == 0.0 for r in wrong.summary().values())


def test_dry_run_counts_tokens_without_calls():
    report = ai_bench.run(None, datasets=bundled()[:2])
    s = report.summary()
    assert report.dry_run and all(r["accuracy"] is None for r in s.values())
    assert all(r["prompt_tokens"] > r["data_tokens"] > 0 for r in s.values())


def test_write_task_validates_output():
    from arkadia.bench.formats import available_formats

    formats = available_formats()
    ds = [
        Dataset(
            "t",
            {"items": [{"id": 1, "n": "a"}, {"id": 2, "n": "b"}, {"id": 3, "n": "c"}]},
            "test",
        )
    ]
    sample = ai_bench._write_sample(ds[0])

    def writer(system, user):
        if "Convert this JSON to AK-Data" in user:
            return formats["akcd"].encode(sample)
        if "Convert this JSON to JSON" in user:
            return "```json\n" + json.dumps(sample) + "\n```"
        return "1. 3"

    report = ai_bench.run(
        ai_bench.Scripted(writer), datasets=ds, formats=["json", "akcd"], write=True
    )
    by = {w.format: w.valid for w in report.writes}
    assert by == {"json": True, "akcd": True}


def test_openai_compatible_provider_against_local_server():
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen["body"] = body
            seen["auth"] = self.headers.get("Authorization")
            out = json.dumps(
                {
                    "choices": [{"message": {"content": "1. 100"}}],
                    "usage": {"prompt_tokens": 321, "completion_tokens": 4},
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        p = ai_bench.OpenAICompatible(
            "test-model", "k", f"http://127.0.0.1:{server.server_port}/v1"
        )
        reply = p.complete("sys", "user")
        assert reply.text == "1. 100" and reply.input_tokens == 321
        assert seen["body"]["model"] == "test-model" and seen["auth"] == "Bearer k"
        assert seen["body"]["temperature"] == 0
    finally:
        server.shutdown()


def test_provider_from_env(monkeypatch):
    for k in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert ai_bench.provider_from_env() is None
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert isinstance(ai_bench.provider_from_env(), ai_bench.Anthropic)
    p = ai_bench.provider_from_env("ollama", "llama3.1")
    assert isinstance(p, ai_bench.OpenAICompatible) and p.base_url.endswith(":11434/v1")
