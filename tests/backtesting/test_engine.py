from datetime import date, datetime, timezone
from pytest import approx

from stocks_investment.backtesting.engine import BacktestConfig, simulate_equal_weight
from stocks_investment.domain.market import PriceAdjustmentPolicy, PriceBar
from stocks_investment.domain.models import DataProvenance, Ticker
from stocks_investment.domain.research_engine import PointInTimeDataView, UniverseLimitation, UniverseSnapshot


def provenance(available: date) -> DataProvenance:
    return DataProvenance("fixture", "fixture", datetime(2024, 1, 1, tzinfo=timezone.utc), available, filing_date=available)


def test_equal_weight_backtest_uses_explicit_cost_and_universe_limitation() -> None:
    a = Ticker("AAA")
    bars = tuple(PriceBar(a, day, 10 + i, 10 + i, 10 + i, 10 + i, 100, "USD", PriceAdjustmentPolicy.RAW, provenance(date(2024, 1, 1))) for i, day in enumerate((date(2024, 1, 1), date(2024, 1, 2))))
    universe = UniverseSnapshot("test", "2024-01-01-v1", date(2024, 1, 1), (a,), "fixture", limitations=(UniverseLimitation.SURVIVORSHIP_BIAS_LIMITATION,))
    result = simulate_equal_weight(universe, PointInTimeDataView(date(2024, 1, 1), price_data=bars), {date(2024, 1, 1): {"AAA": 80}}, config=BacktestConfig(date(2024, 1, 1), date(2024, 1, 2), transaction_cost=.01))
    assert result.total_return == approx(0.09)
    assert result.survivorship_bias_limited
