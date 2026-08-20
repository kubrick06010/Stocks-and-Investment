from datetime import date, datetime, timezone

import pytest

from stocks_investment.cli import main
from stocks_investment.domain import (
    ResearchRun,
    ResearchRunStatus,
    ThesisClassification,
    ThesisSnapshot,
    Ticker,
)
from stocks_investment.storage import SQLiteStorage


def _history(path) -> None:
    as_of = date(2025, 12, 31)
    created = datetime(2025, 12, 31, tzinfo=timezone.utc)
    run = ResearchRun(
        "run-t0", created, as_of, "balanced", "balanced_v1", "fixture",
        "fixture-v1", as_of, {}, status=ResearchRunStatus.COMPLETED,
    )
    snapshot = ThesisSnapshot(
        "thesis-t0", Ticker("AAA"), run.id, "run-t0:AAA", as_of,
        "structured_thesis_v1", ThesisClassification.WATCH, "Persisted watch thesis",
    )
    with SQLiteStorage(path) as storage:
        storage.save_research_run(run)
        storage.save_thesis_snapshot(snapshot)


@pytest.mark.parametrize("output_format", ("text", "json", "markdown"))
def test_explore_reads_persisted_history_in_all_safe_formats(
    tmp_path, monkeypatch, capsys, output_format
) -> None:
    path = tmp_path / "interactive.db"
    _history(path)
    commands = iter(["stock AAA", "quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(commands))

    assert main(["explore", "--db", str(path), "--format", output_format]) == 0
    output = capsys.readouterr().out
    assert "thesis-t0" in output
    assert "Traceback" not in output


def test_explore_missing_database_fails_without_creating_it(tmp_path, capsys) -> None:
    path = tmp_path / "missing.db"
    with pytest.raises(SystemExit):
        main(["explore", "--db", str(path)])
    assert not path.exists()
    assert "already exist" in capsys.readouterr().err


def test_all_historical_cli_reads_are_now_read_only(tmp_path, capsys) -> None:
    path = tmp_path / "history.db"
    _history(path)
    before = path.read_bytes()

    assert main(["thesis-history", "AAA", "--db", str(path), "--format", "json"]) == 0
    assert "structured_thesis_v1" in capsys.readouterr().out
    assert path.read_bytes() == before


@pytest.mark.parametrize("output_format", ("text", "json", "markdown"))
def test_narrative_cli_is_evidence_bound_and_read_only(tmp_path, capsys, output_format) -> None:
    path = tmp_path / "narrative.db"
    _history(path)
    before = path.read_bytes()

    assert main(["narrative", "AAA", "--db", str(path), "--format", output_format]) == 0
    output = capsys.readouterr().out
    assert "structured_narrative_v1" in output or "Research report" in output
    assert "optional_llm" not in output
    assert path.read_bytes() == before
