from datetime import date

from stocks_investment.domain.research_engine import CriterionStatus
from stocks_investment.fundamentals import Fact, MarketSnapshot, MetricResult, MetricStatus
from stocks_investment.strategies.value.graham import (
    DEFENSIVE_VERSION, ENTERPRISING_VERSION, MODERNIZED_DEFENSIVE_VERSION,
    DefensiveGrahamStrategy, ModernizedDefensiveGrahamStrategy,
    calculate_ncav, calculate_ncav_per_share, evaluate_margin_of_safety,
    evaluate_metric_threshold, evaluate_net_net, interpret_graham_number,
    evaluate_graham_defensive,
)


def test_graham_criteria_are_explainable_and_versioned() -> None:
    results = evaluate_graham_defensive({"revenue": 100, "current_ratio": 2.4, "positive_earnings_years": 10, "eps_growth": 0.2, "pe_ttm": 18, "price_to_book": 1.2}, as_of=date(2025, 1, 1))
    assert len(results) == 6
    assert results[0].status is CriterionStatus.PASS
    assert results[4].status is CriterionStatus.FAIL
    assert results[4].criterion_version == "graham_defensive_historical_v1"


def test_missing_does_not_become_fail() -> None:
    result = evaluate_graham_defensive({}, as_of=date(2025, 1, 1))[0]
    assert result.status is CriterionStatus.INSUFFICIENT_DATA
    assert result.passed is None


def metric(name: str, value: float | None, status: MetricStatus = MetricStatus.VALID) -> MetricResult:
    return MetricResult(name, value if status is MetricStatus.VALID else None, status,
                        date(2025, 1, 1), "TTM", "x", "USD", (name,), version="fixture_v1")


def test_metric_thresholds_preserve_boundary_and_invalid_semantics() -> None:
    assert evaluate_metric_threshold(metric("pe_ttm", 15), 15).status is CriterionStatus.PASS
    assert evaluate_metric_threshold(metric("pe_ttm", 15.01), 15).status is CriterionStatus.FAIL
    missing = evaluate_metric_threshold(metric("pe_ttm", None, MetricStatus.MISSING), 15)
    assert missing.status is CriterionStatus.INSUFFICIENT_DATA and missing.passed is None
    assert missing.source_observations[0].calculation_version == "fundamentals-b1-v1" or missing.source_observations[0].calculation_version == "fixture_v1"


def test_literal_and_modernized_strategy_versions_are_distinct() -> None:
    data = {"revenue": 100, "current_ratio": 1.7, "positive_earnings_years": 10,
            "eps_growth": 0.2, "pe_ttm": 18, "price_to_book": 1.2}
    literal = DefensiveGrahamStrategy().evaluate(data, as_of=date(2025, 1, 1))
    modern = ModernizedDefensiveGrahamStrategy().evaluate(data, as_of=date(2025, 1, 1))
    assert literal[1].status is CriterionStatus.FAIL
    assert modern[1].status is CriterionStatus.PASS
    assert literal[1].criterion_version == DEFENSIVE_VERSION
    assert modern[1].criterion_version == MODERNIZED_DEFENSIVE_VERSION
    assert ENTERPRISING_VERSION != DEFENSIVE_VERSION


def test_ncav_net_net_and_negative_semantics() -> None:
    as_of = date(2025, 1, 1)
    rows = [Fact("current_assets", 100, date(2024, 1, 1), as_of, "annual", "USD", "USD"),
            Fact("total_liabilities", 40, date(2024, 1, 1), as_of, "annual", "USD", "USD")]
    ncav = calculate_ncav(rows, as_of=as_of)
    per_share = calculate_ncav_per_share(ncav, MarketSnapshot(20, 2, as_of, "USD"))
    assert ncav.value == 60 and per_share.value == 30
    assert evaluate_net_net(per_share, 20).status is CriterionStatus.PASS
    assert evaluate_net_net(per_share, 21).status is CriterionStatus.FAIL
    negative = calculate_ncav([rows[0], Fact("total_liabilities", 120, date(2024, 1, 1), as_of, "annual", "USD", "USD")], as_of=as_of)
    assert evaluate_net_net(calculate_ncav_per_share(negative, MarketSnapshot(20, 2, as_of, "USD")), 1).status is CriterionStatus.NOT_APPLICABLE


def test_graham_number_margin_and_decomposition() -> None:
    result = interpret_graham_number(metric("graham_number", 30), 20)
    assert result.status is CriterionStatus.PASS
    assert result.source_observations[0].source_metric == "graham_number"
    assert evaluate_margin_of_safety(metric("intrinsic_value", 30), 20).status is CriterionStatus.PASS
    assert evaluate_margin_of_safety(metric("intrinsic_value", 30), 25).status is CriterionStatus.FAIL
