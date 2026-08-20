from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from stocks_investment.domain import (
    AnalysisStatus,
    CompositeScore,
    CriterionResult,
    CriterionStatus,
    DataProvenance,
    FactorObservation,
    FactorScore,
    MetricObservation,
    MetricStatus,
    MissingDataPolicy,
    Period,
    PointInTimeDataView,
    PriceAdjustmentPolicy,
    PriceBar,
    Ticker,
    UniverseLimitation,
    UniverseSnapshot,
)


AS_OF = date(2025, 5, 3)


def provenance(*, available: date = AS_OF) -> DataProvenance:
    return DataProvenance(
        source="fixture",
        provider="contract-test",
        retrieved_at=datetime(2025, 5, 3, tzinfo=timezone.utc),
        effective_date=available,
        available_at=datetime.combine(available, datetime.min.time(), tzinfo=timezone.utc),
        filing_date=available,
        period=Period(date(2025, 1, 1), date(2025, 3, 31), "quarter"),
        period_end=date(2025, 3, 31),
        currency="USD",
        units="USD",
    )


def factor(name: str = "pe", value: float | None = 12.0, status: AnalysisStatus = AnalysisStatus.VALID) -> FactorObservation:
    return FactorObservation(name, value, status, "multiple", AS_OF, "TTM", "pe_ttm_v1")


def test_factor_observation_preserves_status_without_zero_coercion() -> None:
    observation = factor(value=None, status=AnalysisStatus.NOT_MEANINGFUL)
    assert observation.value is None
    assert observation.status is AnalysisStatus.NOT_MEANINGFUL
    with pytest.raises(ValueError):
        factor(value=0.0, status=AnalysisStatus.MISSING)


def test_factor_score_preserves_decomposable_observations() -> None:
    observation = factor()
    score = FactorScore("value", "value_v1", 84.0, AnalysisStatus.VALID, 0.3, (observation,), "moderate valuation")
    assert score.observations == (observation,)
    assert score.score == 84.0


def test_composite_score_is_immutable_and_deterministic_from_supplied_components() -> None:
    component = FactorScore("value", "value_v1", 80.0, AnalysisStatus.VALID, 1.0, (factor(),), "ok")
    first = CompositeScore("test", "test_v1", (component,), {"value": 1.0}, MissingDataPolicy.FAIL, 80.0, AnalysisStatus.VALID, AS_OF)
    second = CompositeScore("test", "test_v1", (component,), {"value": 1.0}, MissingDataPolicy.FAIL, 80.0, AnalysisStatus.VALID, AS_OF)
    assert first == second
    with pytest.raises(AttributeError):
        first.final_score = 1  # type: ignore[misc]


def test_missing_data_policy_is_persisted_and_criterion_distinguishes_missing_from_fail() -> None:
    score = CompositeScore("test", "test_v1", (), {}, MissingDataPolicy.INSUFFICIENT_DATA, None, AnalysisStatus.INSUFFICIENT_HISTORY, AS_OF)
    assert score.missing_data_policy is MissingDataPolicy.INSUFFICIENT_DATA
    failed = CriterionResult("pe_limit", "pe_v1", 20.0, 15.0, CriterionStatus.FAIL, False, "above threshold")
    missing = CriterionResult("pe_limit", "pe_v1", None, 15.0, CriterionStatus.INSUFFICIENT_DATA, None, "EPS unavailable")
    assert failed.passed is False
    assert missing.passed is None


def test_strategy_identity_is_part_of_the_immutable_result_contract() -> None:
    component = FactorScore("value", "value_v1", 80.0, AnalysisStatus.VALID, 1.0, (factor(),), "ok")
    result = CompositeScore("balanced_value_quality", "balanced_value_quality_v1", (component,), {"value": 1.0}, MissingDataPolicy.FAIL, 80.0, AnalysisStatus.VALID, AS_OF)
    assert (result.strategy_name, result.strategy_version) == ("balanced_value_quality", "balanced_value_quality_v1")


def test_universe_snapshot_is_dated_versioned_deterministic_and_can_record_bias() -> None:
    snapshot = UniverseSnapshot(
        "sp500", "sp500-2025-05-03", AS_OF, (Ticker("AAPL"), Ticker("MSFT")), "fixture",
        limitations=(UniverseLimitation.SURVIVORSHIP_BIAS_LIMITATION,),
    )
    assert snapshot.version == "sp500-2025-05-03"
    assert UniverseLimitation.SURVIVORSHIP_BIAS_LIMITATION in snapshot.limitations
    with pytest.raises(ValueError):
        UniverseSnapshot("bad", "v1", AS_OF, (Ticker("MSFT"), Ticker("AAPL")), "fixture")


def test_backtest_data_view_blocks_future_fundamentals_but_outcome_can_be_added_later() -> None:
    future = MetricObservation("revenue", 100.0, MetricStatus.VALID, date(2025, 5, 3), provenance(available=date(2025, 5, 2)))
    old = MetricObservation("revenue", 90.0, MetricStatus.VALID, AS_OF, provenance(available=date(2025, 4, 1)))
    view = PointInTimeDataView(date(2025, 4, 30), {"TEST": (future, old)})
    assert [item.value for item in view.metric_observations(Ticker("TEST"))] == [90.0]
    assert future.value == 100.0  # retained for a later outcome/observation process, not the view


def test_price_information_barrier_uses_canonical_availability() -> None:
    ticker = Ticker("TEST")
    bar = PriceBar(ticker, date(2025, 5, 2), Decimal("10"), Decimal("10"), Decimal("10"), Decimal("10"), 1, "USD", PriceAdjustmentPolicy.RAW, provenance(available=date(2025, 5, 2)))
    assert PointInTimeDataView(date(2025, 5, 1), price_data=(bar,)).prices(ticker, date(2025, 1, 1), AS_OF) == ()
    assert len(PointInTimeDataView(AS_OF, price_data=(bar,)).prices(ticker, date(2025, 1, 1), AS_OF)) == 1
