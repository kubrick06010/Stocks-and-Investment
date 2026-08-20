from datetime import date, datetime, timezone
import json

import pytest

from stocks_investment.data.providers._http import HttpResponse
from stocks_investment.data.providers.sec_filings import SecFilingProviderError, SecFilingsProvider
from stocks_investment.domain import Ticker


def _submissions(*, filing_date: str = "2025-05-02", acceptance: str = "2025-05-02T16:00:00") -> bytes:
    recent = {
        "accessionNumber": ["0000123456-25-000001"],
        "filingDate": [filing_date],
        "acceptanceDateTime": [acceptance],
        "reportDate": ["2025-03-31"],
        "form": ["10-Q"],
        "primaryDocument": ["quarterly.htm"],
    }
    return json.dumps({"filings": {"recent": recent}}).encode()


def test_sec_filing_provider_normalizes_metadata_content_and_pit() -> None:
    content = b"<!doctype html><html><body>Quarterly filing</body></html>"
    calls: list[str] = []

    def transport(url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
        calls.append(url)
        assert headers["User-Agent"] == "research-tests test@example.com"
        return HttpResponse(_submissions() if "submissions" in url else content, 200)

    provider = SecFilingsProvider(
        user_agent="research-tests test@example.com",
        ticker_map={"TEST": "123456"},
        transport=transport,
        clock=lambda: datetime(2025, 6, 1, tzinfo=timezone.utc),
        retries=0,
    )
    filing = next(iter(provider.filings(Ticker("TEST"), date(2025, 5, 2))))

    assert filing.cik == "0000123456"
    assert filing.accession_number == "0000123456-25-000001"
    assert filing.source_url == (
        "https://www.sec.gov/Archives/edgar/data/123456/000012345625000001/quarterly.htm"
    )
    assert filing.mime_type == "text/html"
    assert filing.content_hash
    assert filing.provenance.available_at == filing.available_at
    assert provider.content(filing) == content
    assert calls.count(filing.source_url) == 1


def test_acceptance_timestamp_controls_as_of_visibility() -> None:
    content = b"plain SEC filing text"

    def transport(url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
        return HttpResponse(_submissions(acceptance="2025-05-02T16:00:00") if "submissions" in url else content, 200)

    provider = SecFilingsProvider(
        user_agent="test test@example.com",
        ticker_map={"TEST": "1"},
        transport=transport,
        clock=lambda: datetime(2025, 6, 1, tzinfo=timezone.utc),
        retries=0,
    )
    assert tuple(provider.filings(Ticker("TEST"), date(2025, 5, 1))) == ()
    assert len(tuple(provider.filings(Ticker("TEST"), date(2025, 5, 2)))) == 1


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (b"\x00binary", "binary"),
        (b"{\"not\":\"a filing\"}", "MIME"),
    ],
)
def test_non_text_or_non_allowlisted_content_is_rejected(body: bytes, message: str) -> None:
    def transport(url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
        return HttpResponse(_submissions() if "submissions" in url else body, 200)

    provider = SecFilingsProvider(
        user_agent="test test@example.com",
        ticker_map={"TEST": "1"},
        transport=transport,
        clock=lambda: datetime(2025, 6, 1, tzinfo=timezone.utc),
        retries=0,
    )
    with pytest.raises(SecFilingProviderError, match=message):
        tuple(provider.filings(Ticker("TEST"), date(2025, 5, 2)))


def test_limits_and_user_agent_are_required() -> None:
    with pytest.raises(ValueError, match="user_agent"):
        SecFilingsProvider(user_agent="missing-contact")
    with pytest.raises(ValueError, match="limits"):
        SecFilingsProvider(user_agent="test test@example.com", max_content_bytes=0)
