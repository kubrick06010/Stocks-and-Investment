from __future__ import annotations

import math

import pytest

from stocks_investment.portfolio_construction.trades import reconcile_target_trades


def test_zero_turnover_is_identity_safe_and_free() -> None:
    result = reconcile_target_trades({"BBB": 0.4, "AAA": 0.6}, {"AAA": 0.6, "BBB": 0.4}, 100_000, 0.01)

    assert result.gross_traded_notional == pytest.approx(0)
    assert result.turnover == pytest.approx(0)
    assert result.estimated_transaction_cost == pytest.approx(0)
    assert result.cash_after == pytest.approx(0)
    assert tuple(trade.ticker.symbol for trade in result.trades) == ("AAA", "BBB")


def test_partial_turnover_counts_only_changed_tickers() -> None:
    result = reconcile_target_trades({"AAA": 0.5, "BBB": 0.4}, {"AAA": 0.5, "CCC": 0.4}, 100_000, 0.01)

    assert [(t.ticker.symbol, t.traded_notional) for t in result.trades] == [
        ("AAA", 0), ("BBB", 40_000), ("CCC", 40_000)
    ]
    assert result.gross_traded_notional == pytest.approx(80_000)
    assert result.turnover == pytest.approx(0.8)
    assert result.estimated_transaction_cost == pytest.approx(800)
    assert result.cash_after == pytest.approx(9_200)


def test_full_turnover_with_cash_buffer_reconciles_capital_and_cost() -> None:
    result = reconcile_target_trades({"AAA": 0.8}, {"BBB": 0.8}, 100_000, 0.002)

    assert result.gross_traded_notional == pytest.approx(160_000)
    assert result.estimated_transaction_cost == pytest.approx(320)
    assert result.invested_after == pytest.approx(80_000)
    assert result.cash_after == pytest.approx(19_680)
    assert result.capital_before == pytest.approx(result.invested_after + result.cash_after + result.estimated_transaction_cost)


def test_negative_or_nonfinite_inputs_are_rejected() -> None:
    with pytest.raises(ValueError):
        reconcile_target_trades({"AAA": -0.1}, {}, 100, 0)
    with pytest.raises(ValueError):
        reconcile_target_trades({}, {"AAA": 1.1}, 100, 0)
    with pytest.raises(ValueError):
        reconcile_target_trades({}, {"AAA": 1}, math.inf, 0)
    with pytest.raises(ValueError):
        reconcile_target_trades({}, {"AAA": 1}, 100, math.nan)


def test_union_preserves_ticker_identity_when_middle_security_is_unchanged_or_removed() -> None:
    result = reconcile_target_trades(
        {"AAA": 0.2, "BBB": 0.3, "CCC": 0.5},
        {"AAA": 0.4, "CCC": 0.6},
        1_000,
        0,
    )

    by_symbol = {trade.ticker.symbol: trade for trade in result.trades}
    assert by_symbol["AAA"].traded_notional == pytest.approx(200)
    assert by_symbol["BBB"].traded_notional == pytest.approx(300)
    assert by_symbol["CCC"].traded_notional == pytest.approx(100)


def test_duplicate_case_insensitive_identity_is_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate ticker identity"):
        reconcile_target_trades({"AAA": 0.2, "aaa": 0.3}, {}, 100, 0)
