from datetime import date

import pytest

from stocks_investment.domain import FactorOutcomeObservation, Ticker
from stocks_investment.domain.statistical_validation import StatisticalStatus
from stocks_investment.statistical_validation.robustness import (
    summarize_explicit_slices,
    turnover_adjusted_efficacy,
)


def _row(symbol: str, as_of: date, score: float, excess: float, **identity: str) -> FactorOutcomeObservation:
    benchmark_return = 0.05
    return FactorOutcomeObservation(
        "quality", identity.get("factor_version", "quality_v1"), f"run-{as_of}-{symbol}",
        Ticker(symbol), as_of, score, identity.get("horizon", "12M"),
        benchmark_return + excess, benchmark_return, excess, "measured",
        identity.get("universe", "US-v1"), identity.get("benchmark", "SPY"),
        identity.get("currency", "USD"), "annual",
    )


def test_explicit_regime_slices_are_identity_safe_and_deterministic() -> None:
    rows = (
        _row("BBB", date(2021, 1, 1), 20, -0.02),
        _row("AAA", date(2021, 1, 1), 80, 0.08),
        _row("BBB", date(2022, 1, 1), 30, -0.01),
        _row("AAA", date(2022, 1, 1), 90, 0.09),
    )
    labels = {
        ("AAA", date(2021, 1, 1)): "low_volatility",
        ("BBB", date(2021, 1, 1)): "low_volatility",
        ("AAA", date(2022, 1, 1)): "high_volatility",
        ("BBB", date(2022, 1, 1)): "high_volatility",
    }
    first = summarize_explicit_slices(rows, labels, minimum_sample_size=2)
    second = summarize_explicit_slices(tuple(reversed(rows)), labels, minimum_sample_size=2)
    assert first == second
    assert tuple(item.label for item in first.slices) == ("high_volatility", "low_volatility")
    assert all(item.status is StatisticalStatus.VALID for item in first.slices)
    assert all(item.rank_association == pytest.approx(1.0) for item in first.slices)


def test_missing_labels_and_outcomes_are_explicit_in_counts() -> None:
    complete = _row("AAA", date(2021, 1, 1), 80, 0.08)
    missing = FactorOutcomeObservation(
        "quality", "quality_v1", "missing", Ticker("BBB"), date(2021, 1, 1), 20,
        "12M", None, None, None, "missing", "US-v1", "SPY", "USD", "annual",
    )
    summary = summarize_explicit_slices(
        (complete, missing), {("AAA", date(2021, 1, 1)): "2021"}, minimum_sample_size=2
    )
    assert summary.eligible_observations == 2
    assert summary.labelled_observations == 1
    assert summary.slices[0].status is StatisticalStatus.INSUFFICIENT_SAMPLE


@pytest.mark.parametrize("field,value", [
    ("factor_version", "quality_v2"), ("horizon", "3M"), ("universe", "EU-v1"),
    ("benchmark", "QQQ"), ("currency", "EUR"),
])
def test_mixed_cohort_identity_is_rejected(field: str, value: str) -> None:
    base = _row("AAA", date(2021, 1, 1), 80, 0.08)
    mixed = _row("BBB", date(2021, 1, 1), 20, -0.02, **{field: value})
    with pytest.raises(ValueError, match="incompatible cohort identity"):
        summarize_explicit_slices((base, mixed), {}, minimum_sample_size=2)


def test_turnover_adjusted_spread_has_hand_checked_cost_economics() -> None:
    result = turnover_adjusted_efficacy(
        0.08, gross_traded_notional=600.0, portfolio_capital=1000.0,
        transaction_cost_rate=0.01,
    )
    # Hand derivation: turnover 600/1000=.60; cost=600*.01=6;
    # return impact=6/1000=.006; net spread=.08-.006=.074.
    assert result.turnover == pytest.approx(0.6)
    assert result.transaction_cost == pytest.approx(6.0)
    assert result.cost_return_impact == pytest.approx(0.006)
    assert result.net_spread == pytest.approx(0.074)


def test_zero_turnover_has_no_cost_and_invalid_money_is_rejected() -> None:
    result = turnover_adjusted_efficacy(
        0.03, gross_traded_notional=0, portfolio_capital=1000, transaction_cost_rate=0.02
    )
    assert result.net_spread == result.gross_spread == 0.03
    with pytest.raises(ValueError, match="positive"):
        turnover_adjusted_efficacy(
            0.03, gross_traded_notional=0, portfolio_capital=0, transaction_cost_rate=0.02
        )
