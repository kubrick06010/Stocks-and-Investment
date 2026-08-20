from datetime import date, datetime, timezone

import pytest

from stocks_investment.domain import DataProvenance, MetricObservation, MetricStatus, Ticker


def provenance(*, available: date = date(2025, 1, 1)) -> DataProvenance:
    return DataProvenance(
        source="fixture",
        provider="test",
        retrieved_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
        effective_date=available,
        available_at=datetime.combine(available, datetime.min.time(), tzinfo=timezone.utc),
    )


def test_ticker_is_normalized() -> None:
    assert Ticker(" aapl ").symbol == "AAPL"


def test_metric_rejects_future_provenance() -> None:
    with pytest.raises(ValueError, match="not available"):
        MetricObservation(
            name="pe",
            value=10.0,
            status=MetricStatus.VALID,
            as_of=date(2024, 12, 31),
            provenance=provenance(available=date(2025, 1, 1)),
        )


def test_metric_distinguishes_missing_from_zero() -> None:
    missing = MetricObservation(
        name="fcf",
        value=None,
        status=MetricStatus.MISSING,
        as_of=date(2025, 1, 1),
        provenance=provenance(),
    )
    assert missing.value is None
