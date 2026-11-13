"""AI benchmark providers: Anthropic retries without `temperature` when a
model rejects it, and requests wait as long as a rate limit (429) asks."""

import pytest

from arkadia.bench import ai_bench


def test_retries_without_temperature(monkeypatch):
    calls = []

    def post(url, headers, body):
        calls.append(dict(body))
        if "temperature" in body:
            raise RuntimeError(
                'HTTP 400 from x: "`temperature` is deprecated for this model"'
            )
        return {
            "content": [{"type": "text", "text": "42"}],
            "usage": {"input_tokens": 5},
        }

    monkeypatch.setattr(ai_bench, "_post", post)
    provider = ai_bench.Anthropic("claude-sonnet-5-5", api_key="k")
    assert provider.complete("s", "u", 10).text == "42"
    assert provider.complete("s", "u", 10).text == "42"
    # one refusal, then every request goes without temperature, with room to reason
    assert ["temperature" in c for c in calls] == [True, False, False]
    assert calls[1]["max_tokens"] == 10 + ai_bench.REASONING_BUDGET


def test_parallel_refusals_all_retry(monkeypatch):
    provider = ai_bench.Anthropic("claude-sonnet-5-5", api_key="k")
    calls = []

    def post(url, headers, body):
        calls.append(dict(body))
        if "temperature" in body:
            # Another thread got its refusal first and already switched the flag.
            provider.reasoning_model = True
            raise RuntimeError('HTTP 400: "`temperature` is deprecated for this model"')
        return {"content": [{"type": "text", "text": "ok"}]}

    monkeypatch.setattr(ai_bench, "_post", post)
    assert provider.complete("s", "u", 10).text == "ok"
    assert ["temperature" in c for c in calls] == [True, False]


def test_empty_reply_cut_by_reasoning_is_retried(monkeypatch):
    calls = []

    def post(url, headers, body):
        calls.append(dict(body))
        if body["max_tokens"] < 100:
            return {
                "content": [{"type": "thinking", "thinking": "..."}],
                "stop_reason": "max_tokens",
            }
        return {"content": [{"type": "text", "text": "7"}], "stop_reason": "end_turn"}

    monkeypatch.setattr(ai_bench, "_post", post)
    provider = ai_bench.Anthropic("claude-x", api_key="k")
    assert provider.complete("s", "u", 40).text == "7"
    assert provider.reasoning_model is True
    assert [c["max_tokens"] for c in calls] == [40, 40 + ai_bench.REASONING_BUDGET]


def test_keeps_temperature_when_accepted(monkeypatch):
    calls = []
    monkeypatch.setattr(
        ai_bench,
        "_post",
        lambda url, headers, body: (
            calls.append(body) or {"content": [{"type": "text", "text": "ok"}]}
        ),
    )
    ai_bench.Anthropic("claude-haiku", api_key="k").complete("s", "u")
    assert calls[0]["temperature"] == 0


def test_other_errors_are_raised(monkeypatch):
    def post(url, headers, body):
        raise RuntimeError("HTTP 400 from x: max_tokens is too large")

    monkeypatch.setattr(ai_bench, "_post", post)
    with pytest.raises(RuntimeError):
        ai_bench.Anthropic("m", api_key="k").complete("s", "u")


def _http_error(code, body, retry_after=None):
    import io
    import urllib.error
    from email.message import Message

    headers = Message()
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return urllib.error.HTTPError("u", code, "err", headers, io.BytesIO(body.encode()))


def test_post_waits_on_rate_limit(monkeypatch):
    import io

    responses = [
        _http_error(429, '{"error": {"details": [{"retryDelay": "7s"}]}}'),
        _http_error(429, "slow down", retry_after=3),
    ]
    slept = []

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(req, timeout):
        if responses:
            raise responses.pop(0)
        return Resp(b'{"ok": true}')

    monkeypatch.setattr(ai_bench.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(ai_bench.time, "sleep", slept.append)
    assert ai_bench._post("https://example.test/v1", {}, {}) == {"ok": True}
    # Google's retryDelay and the Retry-After header are honoured
    assert slept == [7.0, 4.0]


def test_post_gives_up_after_rate_limit_retries(monkeypatch):
    monkeypatch.setattr(
        ai_bench.urllib.request,
        "urlopen",
        lambda req, timeout: (_ for _ in ()).throw(_http_error(429, "quota")),
    )
    monkeypatch.setattr(ai_bench.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError, match="HTTP 429"):
        ai_bench._post("https://example.test/v1", {}, {})


def test_openai_compatible_empty_reply_cut_by_reasoning_is_retried(monkeypatch):
    calls = []

    def post(url, headers, body):
        calls.append(dict(body))
        if "temperature" in body:
            return {
                "choices": [
                    {"message": {"content": "Step 1: ..."}, "finish_reason": "length"}
                ]
            }
        return {"choices": [{"message": {"content": "7"}, "finish_reason": "stop"}]}

    monkeypatch.setattr(ai_bench, "_post", post)
    gemini = ai_bench.OpenAICompatible(
        "gemini-3.8-flash",
        api_key="k",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
    )
    assert gemini.complete("s", "u", 40).text == "7"
    # Gemini keeps max_tokens (only OpenAI calls it max_completion_tokens)
    assert calls[1]["max_tokens"] == 40 + ai_bench.REASONING_BUDGET
    assert "temperature" not in calls[1]


def test_openai_reasoning_uses_max_completion_tokens():
    gpt = ai_bench.OpenAICompatible("gpt-5.5", api_key="k")
    body = gpt._body("s", "u", 40)
    assert body["max_completion_tokens"] == 40 + ai_bench.REASONING_BUDGET
    assert "temperature" not in body and "max_tokens" not in body
