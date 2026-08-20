import sqlite3

from stocks_investment.storage import SQLiteStorage


def test_empty_database_migrates_and_reopens_safely(tmp_path) -> None:
    path = tmp_path / "research.db"
    with SQLiteStorage(path) as storage:
        tables = {
            row[0]
            for row in storage._connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {"schema_meta", "raw_payloads", "metric_observations", "research_runs", "research_results"} <= tables
    with SQLiteStorage(path) as storage:
        version = storage._connection.execute(
            "SELECT value FROM schema_meta WHERE key = 'version'"
        ).fetchone()[0]
        assert version == "10"


def test_schema_is_usable_by_sqlite_after_close(tmp_path) -> None:
    path = tmp_path / "research.db"
    with SQLiteStorage(path):
        pass
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM research_runs").fetchone()[0] == 0


def test_wave_d_cohort_migration_is_additive_over_version_five_database(tmp_path) -> None:
    path = tmp_path / "version-five.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO schema_meta VALUES ('version', '5')")
        connection.execute(
            """CREATE TABLE raw_payloads (
                content_hash TEXT PRIMARY KEY, provider TEXT NOT NULL, endpoint TEXT NOT NULL,
                parameters_json TEXT NOT NULL, payload TEXT NOT NULL, retrieved_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            "INSERT INTO raw_payloads VALUES ('sentinel', 'fixture', 'old', '{}', '{}', '2025-01-01T00:00:00+00:00')"
        )
    with SQLiteStorage(path) as storage:
        version = storage._connection.execute(
            "SELECT value FROM schema_meta WHERE key='version'"
        ).fetchone()[0]
        preserved = storage._connection.execute(
            "SELECT provider FROM raw_payloads WHERE content_hash='sentinel'"
        ).fetchone()[0]
        cohort_table = storage._connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='factor_outcome_observations'"
        ).fetchone()
    assert version == "10"
    assert preserved == "fixture"
    assert cohort_table is not None


def test_wave_e_migration_is_additive_over_version_six_database(tmp_path) -> None:
    path = tmp_path / "version-six.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO schema_meta VALUES ('version', '6')")
        connection.execute(
            """CREATE TABLE raw_payloads (
                content_hash TEXT PRIMARY KEY, provider TEXT NOT NULL, endpoint TEXT NOT NULL,
                parameters_json TEXT NOT NULL, payload TEXT NOT NULL, retrieved_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            "INSERT INTO raw_payloads VALUES ('sentinel-v6', 'fixture', 'old', '{}', '{}', '2025-01-01T00:00:00+00:00')"
        )

    with SQLiteStorage(path) as storage:
        version = storage._connection.execute(
            "SELECT value FROM schema_meta WHERE key='version'"
        ).fetchone()[0]
        preserved = storage._connection.execute(
            "SELECT provider FROM raw_payloads WHERE content_hash='sentinel-v6'"
        ).fetchone()[0]
        new_tables = {
            row[0]
            for row in storage._connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        storage._migrate()
        repeated_version = storage._connection.execute(
            "SELECT value FROM schema_meta WHERE key='version'"
        ).fetchone()[0]

    assert version == repeated_version == "10"
    assert preserved == "fixture"
    assert {
        "statistical_dataset_manifests",
        "validation_cohorts",
        "statistical_validation_runs",
        "factor_validation_summaries",
    } <= new_tables


def test_wave_e2_migration_is_additive_over_version_seven_database(tmp_path) -> None:
    path = tmp_path / "version-seven.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO schema_meta VALUES ('version', '7')")
        connection.execute(
            """CREATE TABLE raw_payloads (
                content_hash TEXT PRIMARY KEY, provider TEXT NOT NULL, endpoint TEXT NOT NULL,
                parameters_json TEXT NOT NULL, payload TEXT NOT NULL, retrieved_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            "INSERT INTO raw_payloads VALUES ('e2-sentinel', 'fixture', 'old', '{}', '{}', '2025-01-01T00:00:00+00:00')"
        )
    with SQLiteStorage(path) as storage:
        assert storage._connection.execute(
            "SELECT provider FROM raw_payloads WHERE content_hash='e2-sentinel'"
        ).fetchone()[0] == "fixture"
        assert storage._connection.execute(
            "SELECT value FROM schema_meta WHERE key='version'"
        ).fetchone()[0] == "10"
        tables = {
            row[0]
            for row in storage._connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        storage._migrate()
    assert {
        "filing_documents", "filing_sections", "qualitative_claims",
        "filing_section_changes", "filing_evidence_snapshots",
    } <= tables


def test_wave_e3_migration_is_additive_over_version_eight_database(tmp_path) -> None:
    path = tmp_path / "version-eight.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO schema_meta VALUES ('version', '8')")
        connection.execute(
            """CREATE TABLE raw_payloads (
                content_hash TEXT PRIMARY KEY, provider TEXT NOT NULL, endpoint TEXT NOT NULL,
                parameters_json TEXT NOT NULL, payload TEXT NOT NULL, retrieved_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            "INSERT INTO raw_payloads VALUES "
            "('e3-sentinel', 'fixture', 'old', '{}', '{}', '2026-01-01T00:00:00+00:00')"
        )
    with SQLiteStorage(path) as storage:
        tables = {
            row[0]
            for row in storage._connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert storage._connection.execute(
            "SELECT provider FROM raw_payloads WHERE content_hash='e3-sentinel'"
        ).fetchone()[0] == "fixture"
        assert storage._connection.execute(
            "SELECT value FROM schema_meta WHERE key='version'"
        ).fetchone()[0] == "10"
        storage._migrate()
    assert {"automation_definitions", "automation_triggers", "automation_runs"} <= tables


def test_wave_e4_migration_is_additive_over_version_nine_database(tmp_path) -> None:
    path = tmp_path / "version-nine.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO schema_meta VALUES ('version', '9')")
        connection.execute(
            """CREATE TABLE raw_payloads (
                content_hash TEXT PRIMARY KEY, provider TEXT NOT NULL, endpoint TEXT NOT NULL,
                parameters_json TEXT NOT NULL, payload TEXT NOT NULL, retrieved_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            "INSERT INTO raw_payloads VALUES "
            "('e4-sentinel', 'fixture', 'old', '{}', '{}', '2026-01-01T00:00:00+00:00')"
        )
    with SQLiteStorage(path) as storage:
        tables = {
            row[0]
            for row in storage._connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert storage._connection.execute(
            "SELECT provider FROM raw_payloads WHERE content_hash='e4-sentinel'"
        ).fetchone()[0] == "fixture"
        assert storage._connection.execute(
            "SELECT value FROM schema_meta WHERE key='version'"
        ).fetchone()[0] == "10"
        storage._migrate()
    assert {
        "portfolio_construction_policies",
        "portfolio_construction_requests",
        "portfolio_construction_results",
    } <= tables
