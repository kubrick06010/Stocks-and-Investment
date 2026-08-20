from datetime import date, datetime, timezone

from stocks_investment.domain import ResearchResult, ResearchRun, ResearchRunStatus, Ticker
from stocks_investment.domain.research_engine import (
    AnalysisStatus, CriterionResult, CriterionStatus, FactorObservation, FactorScore,
    ResearchOutcome, UniverseSnapshot,
)
from stocks_investment.storage import SQLiteStorage


def test_universe_components_and_outcome_survive_reopen(tmp_path) -> None:
    created = datetime(2025, 5, 10, tzinfo=timezone.utc)
    run = ResearchRun("run-c5", created, date(2025, 5, 10), "graham", "graham_defensive_literal_v1", "fixture", "fixture-2025-05-10-v1", date(2025, 5, 10), {}, status=ResearchRunStatus.COMPLETED)
    observation = FactorObservation("quality", 84.0, AnalysisStatus.VALID, "score", date(2025, 5, 10), "TTM", "quality_v1")
    factor = FactorScore("quality", "quality_v1", 84.0, AnalysisStatus.VALID, 1.0, (observation,), "strong")
    criterion = CriterionResult("pe", "graham_v1", 12.0, 15.0, CriterionStatus.PASS, True, "within limit")
    result = ResearchResult("run-c5:AAA", run.id, Ticker("AAA"), created, 1, 84.0, "selected", (factor,), (criterion,))
    universe = UniverseSnapshot("fixture", "fixture-2025-05-10-v1", date(2025, 5, 10), (Ticker("AAA"),), "synthetic")
    path = tmp_path / "research.db"
    with SQLiteStorage(path) as storage:
        storage.save_universe_snapshot(universe)
        storage.save_research_run(run)
        storage.save_research_result(result)
        storage.save_research_outcome(ResearchOutcome(result.id, date(2025, 6, 10), "1M", .1, .05, .05))
    with SQLiteStorage(path) as storage:
        loaded_run = storage.load_research_run(run.id)
        loaded_result = storage.load_research_result(result.id)
        assert loaded_run == run
        assert loaded_result is not None
        assert loaded_result.factor_scores[0].score == 84.0
        assert loaded_result.criteria[0].criterion_name == "pe"
        assert storage.load_universe_snapshot("fixture", "fixture-2025-05-10-v1") == universe
        assert storage.load_research_outcomes(result.id)[0].excess_return == .05
