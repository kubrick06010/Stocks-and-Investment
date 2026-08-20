from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from stocks_investment.data import PriceBar, PriceAdjustmentPolicy, ProviderRegistry
from stocks_investment.domain import DataProvenance, Ticker


def provenance() -> DataProvenance:
    return DataProvenance(
        source="fixture",
        provider="test",
        retrieved_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
        effective_date=date(2025, 1, 2),
    )


def test_price_bar_validates_ohlc() -> None:
    bar = PriceBar(
        ticker=Ticker("aapl"),
        session=date(2025, 1, 2),
        open=Decimal("100"),
        high=Decimal("105"),
        low=Decimal("99"),
        close=Decimal("103"),
        volume=1000,
        currency="USD",
        adjustment_policy=PriceAdjustmentPolicy.SPLIT_ADJUSTED,
        provenance=provenance(),
    )
    assert bar.ticker.symbol == "AAPL"


def test_registry_is_explicit_and_rejects_duplicates() -> None:
    registry = ProviderRegistry()
    provider = _Provider()
    registry.register_market_data("fixture", provider)
    assert registry.names() == {"market": ("fixture",), "fundamentals": (), "universe": ()}
    with pytest.raises(ValueError, match="already registered"):
        registry.register_market_data("FIXTURE", provider)


class _Provider:
    name = "fixture"

    def prices(self, ticker, start, end):
        return ()

    def provenance(self, ticker, as_of):
        return ()
