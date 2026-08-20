from datetime import date, datetime, timezone

from stocks_investment.domain import (
    CompositeScore, DataProvenance, MetricObservation, MetricStatus, MissingDataPolicy,
    ResearchOutcome, Ticker, UniverseSnapshot,
)
from stocks_investment.domain.research_engine import AnalysisStatus, CriterionResult, CriterionStatus, FactorObservation, FactorScore, PointInTimeDataView
from stocks_investment.screening import Candidate, ScreeningEngine
from stocks_investment.storage import SQLiteStorage


def _provenance(period_end: date, filing_date: date) -> DataProvenance:
    return DataProvenance("SEC", "synthetic", datetime(2025, 1, 1, tzinfo=timezone.utc), filing_date,
                          filing_date=filing_date, period_end=period_end, units="USD")


def test_historical_screen_reopen_and_future_outcome_are_separate(tmp_path) -> None:
    t0 = date(2024, 12, 31)
    aaa, bbb = Ticker("AAA"), Ticker("BBB")
    observations = (
        MetricObservation("net_income", 10, MetricStatus.VALID, t0, _provenance(date(2024, 12, 31), date(2024, 2, 20))),
        MetricObservation("net_income", 20, MetricStatus.VALID, date(2025, 3, 31), _provenance(date(2025, 3, 31), date(2025, 2, 15))),
    )
    view = PointInTimeDataView(t0, {"AAA": observations})
    assert tuple(item.value for item in view.metric_observations(aaa)) == (10,)
    assert view.metric_observations(bbb) == ()

    def candidate(ticker: Ticker, value: float) -> Candidate:
        factor_observation = FactorObservation("value", value, AnalysisStatus.VALID, "score", t0, "TTM", "value_v1")
        factor = FactorScore("value", "value_v1", value, AnalysisStatus.VALID, 1.0, (factor_observation,), "fixture")
        composite = CompositeScore("balanced_fixture", "balanced_fixture_v1", (factor,), {"value": 1.0}, MissingDataPolicy.FAIL, value, AnalysisStatus.VALID, t0)
        criterion = CriterionResult("graham_pe", "graham_defensive_literal_v1", value, 80, CriterionStatus.PASS, True, "fixture criterion")
        return Candidate(ticker, composite, (factor_observation,), (criterion,))

    universe = UniverseSnapshot("synthetic", "synthetic_t0_v1", t0, (aaa, bbb), "fixture")
    path = tmp_path / "loop.db"
    with SQLiteStorage(path) as storage:
        run = ScreeningEngine(storage).run(universe, [candidate(aaa, 90), candidate(bbb, 60)],
                                           strategy_name="balanced_fixture", strategy_version="balanced_fixture_v1",
                                           created_at=datetime(2024, 12, 31, tzinfo=timezone.utc))
        result_id = f"{run.run.id}:AAA"
        storage.save_research_outcome(ResearchOutcome(result_id, date(2025, 1, 31), "1M", .1, .05, .05))

    with SQLiteStorage(path) as storage:
        restored = storage.load_research_result(result_id)
        assert restored is not None
        assert restored.rank == 1 and restored.composite_score == 90
        assert restored.criteria[0].criterion_name == "graham_pe"
        assert storage.load_universe_snapshot("synthetic", "synthetic_t0_v1") == universe
        assert storage.load_research_outcomes(result_id)[0].forward_return == .1
