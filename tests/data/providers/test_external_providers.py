import json
from datetime import date
from urllib.parse import parse_qs, urlparse

import pytest

from stocks_investment.data.providers import AlphaVantageMarketProvider, SecEdgarProvider
from stocks_investment.data.providers._http import HttpResponse
from stocks_investment.domain import Period, Ticker


def _response(value: dict) -> HttpResponse:
    return HttpResponse(json.dumps(value).encode(), 200)


def test_sec_normalizes_as_filed_fact_and_filters_future_filings() -> None:
    def transport(url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
        assert headers["User-Agent"] == "test-suite test@example.com"
        return _response({"facts": {"us-gaap": {"Revenues": {"units": {"USD": [
            {"val": 900, "start": "2025-01-01", "end": "2025-03-31", "filed": "2025-05-01",
             "accn": "000-test", "form": "10-Q"},
            {"val": 999, "start": "2025-01-01", "end": "2025-03-31", "filed": "2025-08-01",
             "accn": "000-amendment", "form": "10-Q"},
        ]}}}}})

    provider = SecEdgarProvider(user_agent="test-suite test@example.com", ticker_map={"TEST": "123"},
                                transport=transport, retries=0)
    period = Period(date(2025, 1, 1), date(2025, 3, 31), "quarter")
    observations = provider.metric_inputs(Ticker("TEST"), period, date(2025, 6, 1))
    assert [(item.name, item.value) for item in observations] == [("revenue", 900.0)]
    assert observations[0].provenance.raw_identifier == "0000000123/000-test/10-Q/revenue"
    assert provider.metric_inputs(Ticker("TEST"), period, date(2025, 4, 30)) == ()


def test_alpha_vantage_normalizes_bars_and_actions_without_network() -> None:
    def transport(url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
        assert "apikey=secret" in url
        assert parse_qs(urlparse(url).query)["function"] == ["TIME_SERIES_DAILY_ADJUSTED"]
        return _response({"Time Series (Daily)": {
            "2025-01-03": {"1. open": "10", "2. high": "12", "3. low": "9", "4. close": "11",
                            "6. volume": "100", "7. dividend amount": "0.50", "8. split coefficient": "2"},
        }})

    provider = AlphaVantageMarketProvider(api_key="secret", transport=transport, retries=0)
    ticker = Ticker("TEST")
    bars = provider.prices(ticker, date(2025, 1, 1), date(2025, 1, 5))
    actions = provider.corporate_actions(ticker, date(2025, 1, 1), date(2025, 1, 5))
    assert bars[0].close == 11
    assert bars[0].adjustment_policy.value == "raw"
    assert [type(action).__name__ for action in actions] == ["DividendAction", "SplitAction"]
    assert actions[1].factor == 2


@pytest.mark.live
@pytest.mark.skipif("RUN_LIVE_PROVIDER_TESTS" not in __import__("os").environ,
                    reason="live provider tests require explicit RUN_LIVE_PROVIDER_TESTS=1")
def test_live_providers_are_opt_in() -> None:
    """Operational smoke-test placeholder; credentials and identifiers are deployment-owned."""
    pytest.skip("configure provider-specific live smoke tests in deployment")
