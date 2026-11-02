from arkadia.bench.cli import build_parser, network_provider


def test_offline_never_resolves_credentials(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-only")

    def forbidden(*args, **kwargs):
        raise AssertionError("Provider discovery must not happen offline")

    monkeypatch.setattr("arkadia.bench.ai_bench.provider_from_env", forbidden)
    parser = build_parser()
    assert network_provider(parser.parse_args([])) is None
    assert network_provider(parser.parse_args(["--offline", "--model", "any"])) is None


def test_network_requires_explicit_opt_in(monkeypatch, capsys):
    from types import SimpleNamespace

    p = SimpleNamespace(
        model="synthetic-model", base_url="https://example.test/v1?key=not-for-logs"
    )
    monkeypatch.setattr("arkadia.bench.ai_bench.provider_from_env", lambda *a, **k: p)
    assert network_provider(build_parser().parse_args(["--allow-network"])) is p
    output = capsys.readouterr().out
    assert "example.test" in output and "not-for-logs" not in output
