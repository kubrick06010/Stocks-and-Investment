"""Deterministic provider for tests, development, and architecture validation."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from stocks_investment.domain.market import PriceAdjustmentPolicy, PriceBar, Quote
from stocks_investment.domain.models import (
    DataProvenance,
    MetricObservation,
    MetricStatus,
    Period,
    Ticker,
)


class FixtureProvider:
    name = "fixture"
    _prices = {"AAPL": Decimal("190.00"), "TEST": Decimal("42.00")}
    _revenue = {"AAPL": 100_000.0, "TEST": 1_000.0}

    def prices(self, ticker: Ticker, start: date, end: date) -> tuple[PriceBar, ...]:
        if start > end:
            raise ValueError("start must not be after end")
        session = max(start, date(2025, 1, 2))
        if session > end or ticker.symbol not in self._prices:
            return ()
        provenance = self._provenance(ticker, session)
        price = self._prices[ticker.symbol]
        return (
            PriceBar(
                ticker=ticker,
                session=session,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=1_000,
                currency="USD",
                adjustment_policy=PriceAdjustmentPolicy.RAW,
                provenance=provenance,
            ),
        )

    def quote(self, ticker: Ticker, as_of: date) -> Quote | None:
        bars = self.prices(ticker, as_of, as_of)
        if not bars:
            return None
        bar = bars[0]
        return Quote(
            ticker=ticker,
            price=bar.close,
            observed_at=datetime.combine(bar.session, datetime.min.time(), tzinfo=timezone.utc),
            currency=bar.currency,
            provenance=bar.provenance,
        )

    def provenance(self, ticker: Ticker, as_of: date) -> tuple[DataProvenance, ...]:
        return (self._provenance(ticker, as_of),) if ticker.symbol in self._prices else ()

    def metric_inputs(
        self, ticker: Ticker, period: Period, as_of: date
    ) -> tuple[MetricObservation, ...]:
        filing_date = date(2025, 5, 2)
        if ticker.symbol not in self._revenue or as_of < filing_date:
            return ()
        provenance = DataProvenance(
            source="fixture:financials",
            provider=self.name,
            retrieved_at=datetime(2025, 5, 3, tzinfo=timezone.utc),
            effective_date=filing_date,
            available_at=datetime(2025, 5, 2, tzinfo=timezone.utc),
            filing_date=filing_date,
            period=period,
            period_end=period.end,
            currency="USD",
            units="USD",
            raw_identifier=f"fixture/{ticker.symbol}/revenue",
        )
        return (
            MetricObservation(
                name="revenue",
                value=self._revenue[ticker.symbol],
                status=MetricStatus.VALID,
                as_of=filing_date,
                provenance=provenance,
            ),
        )

    def _provenance(self, ticker: Ticker, effective_date: date) -> DataProvenance:
        retrieved_at = datetime.combine(effective_date, datetime.min.time(), tzinfo=timezone.utc)
        return DataProvenance(
            source="fixture:prices",
            provider=self.name,
            retrieved_at=retrieved_at,
            effective_date=effective_date,
            available_at=retrieved_at,
            currency="USD",
            units="USD/share",
            raw_identifier=f"fixture/{ticker.symbol}/price",
        )
