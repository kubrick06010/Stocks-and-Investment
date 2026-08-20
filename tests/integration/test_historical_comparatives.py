from datetime import date, datetime, timezone

from stocks_investment.domain import DataProvenance, MetricObservation, MetricStatus, Period
from stocks_investment.provenance.point_in_time import filter_available, previous_period


def test_prior_period_accessor_respects_public_availability() -> None:
    def row(period_end: date, filing_date: date, value: float) -> MetricObservation:
        return MetricObservation(
            "net_income", value, MetricStatus.VALID, filing_date,
            DataProvenance("SEC", "fixture", datetime(2025, 1, 1, tzinfo=timezone.utc), filing_date,
                           filing_date=filing_date, period_end=period_end,
                           period=Period(period_end.replace(year=period_end.year - 1), period_end, "annual"), units="USD"),
        )
    rows = (row(date(2023, 12, 31), date(2024, 2, 20), 8), row(date(2024, 12, 31), date(2025, 2, 20), 10))
    prior_before_current_filing = previous_period(rows, name="net_income", period_end=date(2024, 12, 31), as_of=date(2025, 2, 10))
    assert prior_before_current_filing is not None and prior_before_current_filing.value == 8
    prior = previous_period(rows, name="net_income", period_end=date(2024, 12, 31), as_of=date(2025, 3, 1))
    assert prior is not None and prior.value == 8
    assert tuple(item.value for item in filter_available(rows, date(2025, 2, 10))) == (8,)
