"""make check: the metadata-trap cases parse, carry the same data in all four forms, and are scored right."""

import pathlib

from arkadia.bench.check import (
    FORMS,
    clean_answer,
    demo_provider,
    main,
    parse_cases,
    run_one,
    same,
    validate,
    verdict,
)

CASES = (
    pathlib.Path(__file__).resolve().parents[2] / "examples" / "meta-traps" / "cases.md"
)


def cases():
    return parse_cases(CASES.read_text(encoding="utf-8"))


def test_five_cases_four_forms_same_data():
    cs = cases()
    assert [c.num for c in cs] == list(range(1, 6))
    for c in cs:
        assert set(c.prompts) == set(FORMS)
        assert c.expected and c.traps
    assert "/* test record */" in cs[3].data["D"]
    assert validate(cs) == []


def test_validate_catches_broken_akdata():
    c = cases()[0]
    c.data["D"] = c.data["D"].replace("<ledger:", "<ledger")
    assert any("1D" in p for p in validate([c]))


def test_answers_are_cleaned_and_compared():
    assert clean_answer("**250**") == "250"
    assert clean_answer("**250** PLN.") == "250"
    assert clean_answer("€53.99") == "53.99"
    assert clean_answer("53.99 EUR") == "53.99"
    assert clean_answer("Let me compute.\nFinal answer: 140.0") == "140.0"
    assert clean_answer("Step 1: 96\nTotal = 96 + 12 + 16 = 124 vCPU-hours") == "124"
    assert clean_answer("250 PLN.") == "250"
    assert same("140.0", "140") and same("1,000", "1000") and not same("1,5", "15")
    assert same("e5, E1", "E1, E5") and not same("E1, E3", "E1, E5")
    c4 = cases()[3]
    assert verdict(c4, "53.99") == "ok"
    assert verdict(c4, "1053.99") == "trap"
    c5 = cases()[4]
    assert verdict(c5, "E1, E5") == "ok"
    assert verdict(c5, "E1, E4, E5") == "trap"
    assert verdict(c5, "E2") == "wrong"


def test_one_call_and_errors_do_not_stop_the_run():
    c = cases()[0]
    p = demo_provider([c], "openai", "demo", 1)
    r = run_one(p, c, "D", 0, 10)
    assert r.verdict in ("ok", "trap", "wrong") and r.answer

    class Broken:
        name, model = "openai", "x"

        def complete(self, *a, **k):
            raise RuntimeError("HTTP 401")

    r = run_one(Broken(), c, "A", 0, 10)
    assert r.verdict == "error" and "401" in r.error


def test_dry_run_and_demo_exit_cleanly(capsys):
    assert main(["--dry-run", "--no-color", "--file", str(CASES)]) == 0
    assert main(["--demo", "--no-color", "--file", str(CASES), "--cases", "1,2"]) == 0
    out = capsys.readouterr().out
    assert "SUMMARY" in out and "What the notes change" in out


def test_empty_env_near_does_not_hide_the_root_one(tmp_path, monkeypatch):
    from arkadia.bench import check

    (tmp_path / ".env").write_text("CHECK_TEST_KEY=from-root\n")
    sub = tmp_path / "python"
    sub.mkdir()
    (sub / ".env").write_text("")
    monkeypatch.chdir(sub)
    monkeypatch.delenv("CHECK_TEST_KEY", raising=False)
    files = check.load_env()
    assert (tmp_path / ".env").resolve() in files
    assert check.os.environ["CHECK_TEST_KEY"] == "from-root"
    monkeypatch.delenv("CHECK_TEST_KEY")


def test_prompts_are_printed_and_written(tmp_path, capsys):
    assert (
        main(
            [
                "--demo",
                "--no-color",
                "--file",
                str(CASES),
                "--cases",
                "2",
                "--out",
                str(tmp_path),
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    c = cases()[1]
    for f in FORMS:
        assert c.prompts[f] in out  # printed exactly as sent, ready to copy
        assert (
            tmp_path / "prompts" / f"02{f}-{FORMS[f].lower().replace('+', '-')}.txt"
        ).read_text().strip() == c.prompts[f]
    assert "### 2D" in (tmp_path / "prompts" / "all.md").read_text()
    assert main(["--show", "all", "--no-color", "--file", str(CASES)]) == 0
    assert capsys.readouterr().out.count("┌─") == 20
