from stocks_investment.backtesting import CorporateActionMode, validate_adjustment_mode
from stocks_investment.domain.market import PriceAdjustmentPolicy
from pytest import raises


def test_total_return_series_rejects_raw_or_explicit_dividend_semantics() -> None:
    validate_adjustment_mode(PriceAdjustmentPolicy.TOTAL_RETURN_ADJUSTED, CorporateActionMode.TOTAL_RETURN_ADJUSTED_NO_DIVIDENDS)
    with raises(ValueError):
        validate_adjustment_mode(PriceAdjustmentPolicy.RAW, CorporateActionMode.TOTAL_RETURN_ADJUSTED_NO_DIVIDENDS)
