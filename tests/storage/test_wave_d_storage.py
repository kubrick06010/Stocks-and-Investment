from datetime import date, datetime, timezone

from stocks_investment.domain import (
    ChangeType, DriverDirection, FactorOutcomeObservation, MonitoringEvent, ResearchChangeEvent, ResearchResult,
    ResearchRun, ResearchRunStatus, SourceReference, ThesisClassification, ThesisDriver,
    ThesisDriverCategory, ThesisSnapshot, Ticker, WatchCondition, WatchlistEntry, WatchlistStatus,
)
from stocks_investment.storage import SQLiteStorage


def test_wave_d_entities_round_trip_and_b_c_records_survive(tmp_path) -> None:
    created = datetime(2025, 1, 1, tzinfo=timezone.utc)
    run = ResearchRun("run-d0", created, date(2025, 1, 1), "fixture", "fixture-v1", "synthetic", "u0", date(2025, 1, 1), {}, status=ResearchRunStatus.COMPLETED)
    result = ResearchResult("run-d0:AAA", run.id, Ticker("AAA"), created, 1, 80, "selected")
    source = SourceReference("research_result", result.id, "composite_score")
    thesis = ThesisSnapshot("thesis-1", Ticker("AAA"), run.id, result.id, run.as_of, "structured_thesis_v1", ThesisClassification.WATCH,
                            "quality strong; valuation demanding", drivers=(ThesisDriver("quality", ThesisDriverCategory.QUALITY, DriverDirection.POSITIVE, .9, "80", source, "strong"),))
    change = ResearchChangeEvent(Ticker("AAA"), "run-d0", "run-d1", date(2025, 1, 1), date(2025, 4, 1), ChangeType.RANK_CHANGE, "rank", 20, 5, 15, "material", (source,))
    condition = WatchCondition("pe_ttm", "<=", 18, "watch-v1")
    entry = WatchlistEntry("watch-1", Ticker("AAA"), created, run.id, result.id, "quality strong, valuation high", WatchlistStatus.ACTIVE, target_conditions=(condition,))
    event = MonitoringEvent(entry.id, "run-d1", date(2025, 4, 1), condition, 23, 17, True, "valuation condition passed")
    factor_outcome = FactorOutcomeObservation(
        "quality", "quality_v1", run.id, Ticker("AAA"), run.as_of, 80, "12M",
        .12, .05, .07, "measured", "synthetic", "SYNTH", "USD", "quarterly",
    )
    path = tmp_path / "wave-d.db"
    with SQLiteStorage(path) as storage:
        storage.save_research_run(run)
        storage.save_research_result(result)
        storage.save_thesis_snapshot(thesis)
        storage.save_change_event(change)
        storage.save_watchlist_entry(entry)
        storage.save_monitoring_event(event)
        storage.save_factor_outcome_observation(factor_outcome)
        # Re-running migration is intentionally exercised by reopening below.
    with SQLiteStorage(path) as storage:
        assert storage.load_research_run(run.id) == run
        assert storage.load_research_result(result.id) == result
        assert storage.load_thesis_snapshot(thesis.id) == thesis
        assert storage.load_change_events(Ticker("AAA")) == (change,)
        assert storage.load_watchlist_entry(entry.id) == entry
        assert storage.load_monitoring_events(entry.id) == (event,)
        assert storage.load_factor_outcome_observations(factor_name="quality") == (factor_outcome,)
        version = storage._connection.execute("SELECT value FROM schema_meta WHERE key='version'").fetchone()[0]
        assert version == "10"
