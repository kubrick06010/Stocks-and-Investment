from datetime import date
from pytest import approx

from stocks_investment.analytics.performance import analyze_returns, time_weighted_return, xirr


def test_deposit_does_not_create_twr_performance() -> None:
    assert time_weighted_return([100, 200, 200], [0, 100, 0]) == 0.0


def test_xirr_and_risk_metrics() -> None:
    result = xirr([(date(2024, 1, 1), -100.0), (date(2025, 1, 1), 110.0)])
    assert abs(result - 0.1) < 0.002
    metrics = analyze_returns([100, 110, 105])
    assert metrics["total_return"] == approx(0.05)
    assert metrics["max_drawdown"] < 0
