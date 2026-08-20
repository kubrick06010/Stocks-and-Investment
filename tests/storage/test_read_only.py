import sqlite3
from datetime import date, datetime, timezone

import pytest

from stocks_investment.domain import ResearchResult, ResearchRun, ResearchRunStatus, Ticker
from stocks_investment.storage import SQLiteStorage
from stocks_investment.storage.read_only import ReadOnlySQLiteStorage, ReadOnlyStorageError


def _migrated_database(tmp_path):
    path = tmp_path / "research.db"
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    run = ResearchRun(
        "readonly-run", created, date(2026, 1, 1), "fixture", "fixture_v1", "synthetic", "u1",
        date(2026, 1, 1), {}, status=ResearchRunStatus.COMPLETED,
    )
    result = ResearchResult("readonly-result", run.id, Ticker("TEST"), created, 1, 77.0, "WATCH")
    with SQLiteStorage(path) as storage:
        storage.save_research_run(run)
        storage.save_research_result(result)
    return path, run, result


def test_inherited_read_methods_work_on_existing_migrated_fixture(tmp_path) -> None:
    path, run, result = _migrated_database(tmp_path)

    with ReadOnlySQLiteStorage(path) as storage:
        assert storage.path == path.resolve()
        assert storage.load_research_run(run.id) == run
        assert storage.load_research_result(result.id) == result
        assert storage._connection.execute("PRAGMA query_only").fetchone()[0] == 1


def test_missing_path_is_not_created(tmp_path) -> None:
    path = tmp_path / "missing.db"
    with pytest.raises(ReadOnlyStorageError):
        ReadOnlySQLiteStorage(path)
    assert not path.exists()


@pytest.mark.parametrize("kind", ["directory", "non_db", "uri", "control"])
def test_invalid_paths_are_rejected(tmp_path, kind: str) -> None:
    if kind == "directory":
        path = tmp_path
    elif kind == "non_db":
        path = tmp_path / "text.db"
        path.write_text("not sqlite")
    elif kind == "uri":
        path = "file:///tmp/research.db"
    else:
        path = str(tmp_path / "bad\x00.db")

    with pytest.raises(ReadOnlyStorageError):
        ReadOnlySQLiteStorage(path)


def test_inherited_write_and_migration_attempts_fail_without_changing_schema(tmp_path) -> None:
    path, run, result = _migrated_database(tmp_path)
    with sqlite3.connect(path) as connection:
        before = connection.execute("SELECT value FROM schema_meta WHERE key = 'version'").fetchone()[0]
        rows_before = connection.execute("SELECT COUNT(*) FROM research_results").fetchone()[0]

    with ReadOnlySQLiteStorage(path) as storage:
        with pytest.raises(sqlite3.OperationalError):
            storage.save_research_result(result)
        with pytest.raises(ReadOnlyStorageError):
            storage._migrate()
        assert storage.load_research_run(run.id) == run

    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT value FROM schema_meta WHERE key = 'version'").fetchone()[0] == before
        assert connection.execute("SELECT COUNT(*) FROM research_results").fetchone()[0] == rows_before


def test_close_reopen_is_deterministic(tmp_path) -> None:
    path, run, result = _migrated_database(tmp_path)
    with ReadOnlySQLiteStorage(path) as storage:
        first = (storage.load_research_run(run.id), storage.load_research_result(result.id))
    with ReadOnlySQLiteStorage(path) as storage:
        second = (storage.load_research_run(run.id), storage.load_research_result(result.id))
    assert second == first


def test_unmigrated_or_wrong_schema_is_rejected_without_mutation(tmp_path) -> None:
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO schema_meta VALUES ('version', '9')")
    before = path.read_bytes()

    with pytest.raises(ReadOnlyStorageError, match="schema must be migrated"):
        ReadOnlySQLiteStorage(path)
    assert path.read_bytes() == before
