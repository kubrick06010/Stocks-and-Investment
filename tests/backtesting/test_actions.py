from pytest import approx, raises

from stocks_investment.backtesting import CorporateActionMode, apply_split_raw, dividend_cash


def test_two_for_one_split_conserves_wealth() -> None:
    quantity, price, wealth = apply_split_raw(100, 20, 2, 1)
    assert quantity == 200
    assert price == 10
    assert quantity * price == approx(wealth)


def test_explicit_dividend_is_cash_and_total_return_guard_blocks_double_count() -> None:
    assert dividend_cash(100, 1, CorporateActionMode.RAW_PRICES_EXPLICIT_ACTIONS) == 100
    with raises(ValueError):
        dividend_cash(100, 1, CorporateActionMode.TOTAL_RETURN_ADJUSTED_NO_DIVIDENDS)
