from datetime import date

from stocks_investment.data.providers import FixtureProvider
from stocks_investment.domain import Period, Ticker


def test_fixture_provider_is_deterministic_and_point_in_time_aware() -> None:
    provider = FixtureProvider()
    ticker = Ticker("AAPL")
    period = Period(date(2025, 1, 1), date(2025, 3, 31), "quarter")
    assert provider.prices(ticker, date(2025, 1, 1), date(2025, 1, 3))[0].close == 190
    assert provider.metric_inputs(ticker, period, date(2025, 4, 30)) == ()
    observations = provider.metric_inputs(ticker, period, date(2025, 5, 3))
    assert observations[0].provenance.filing_date == date(2025, 5, 2)
