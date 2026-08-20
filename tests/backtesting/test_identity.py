from datetime import date, datetime, timezone

from stocks_investment.backtesting.engine import BacktestConfig, simulate_equal_weight
from stocks_investment.domain.market import PriceAdjustmentPolicy, PriceBar
from stocks_investment.domain.models import DataProvenance, Ticker
from stocks_investment.domain.research_engine import PointInTimeDataView, UniverseSnapshot


def _p() -> DataProvenance:
    return DataProvenance("fixture", "fixture", datetime(2024, 1, 1, tzinfo=timezone.utc), date(2024, 1, 1))


def test_missing_middle_ticker_cannot_shift_end_price_identity() -> None:
    symbols = tuple(Ticker(s) for s in ("AAA", "BBB", "CCC"))
    bars = (
        PriceBar(symbols[0], date(2024, 1, 1), 100, 100, 100, 100, 1, "USD", PriceAdjustmentPolicy.RAW, _p()),
        PriceBar(symbols[0], date(2024, 1, 2), 110, 110, 110, 110, 1, "USD", PriceAdjustmentPolicy.RAW, _p()),
        PriceBar(symbols[1], date(2024, 1, 1), 50, 50, 50, 50, 1, "USD", PriceAdjustmentPolicy.RAW, _p()),
        PriceBar(symbols[2], date(2024, 1, 1), 20, 20, 20, 20, 1, "USD", PriceAdjustmentPolicy.RAW, _p()),
        PriceBar(symbols[2], date(2024, 1, 2), 30, 30, 30, 30, 1, "USD", PriceAdjustmentPolicy.RAW, _p()),
    )
    result = simulate_equal_weight(
        UniverseSnapshot("u", "v1", date(2024, 1, 1), symbols, "fixture"),
        PointInTimeDataView(date(2024, 1, 1), price_data=bars),
        {date(2024, 1, 1): {symbol.symbol: 1 for symbol in symbols}},
        config=BacktestConfig(date(2024, 1, 1), date(2024, 1, 2)),
    )
    # BBB has no end price, so the whole date is unavailable; it must not be
    # silently dropped and replaced by CCC's price.
    assert len(result.values) == 1
    assert result.values[0][1] == 1.0
