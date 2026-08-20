"""Independent adversarial review of the Wave E2 filing evidence boundary.

This file is intentionally fenced to tests.  It must never make production
changes to accommodate a failing attack: a red test is evidence of a defect.
"""

from dataclasses import replace
from datetime import date, datetime, timezone
import hashlib
import json

import pytest

from stocks_investment.data.providers._http import HttpResponse
from stocks_investment.data.providers.sec_filings import SecFilingProviderError, SecFilingsProvider
from stocks_investment.domain.filings import (
    ClaimCategory,
    ClaimDirection,
    FilingDocument,
    FilingEvidenceReference,
    FilingForm,
    FilingSectionKind,
)
from stocks_investment.domain.models import DataProvenance, Ticker
from stocks_investment.filings.claims import (
    DisclosedRiskPattern,
    build_analyst_authored_claim,
    build_disclosed_risk_claims,
    normalized_excerpt_hash,
)
from stocks_investment.filings.history import FilingHistoryComparator
from stocks_investment.filings.parser import ParseLimits, SafeFilingParser
from stocks_investment.storage import SQLiteStorage


UTC = timezone.utc


def _filing(
    identifier: str = "f1",
    *,
    mime: str = "text/html",
    available: datetime | None = None,
    period_end: date | None = date(2024, 12, 31),
    content_hash: str = "fixture-document",
) -> FilingDocument:
    timestamp = available or datetime(2025, 5, 2, 16, tzinfo=UTC)
    filed_date = timestamp.date()
    provenance = DataProvenance(
        source="fixture",
        provider="offline-fixture",
        retrieved_at=datetime(2025, 6, 1, tzinfo=UTC),
        effective_date=timestamp.date(),
        available_at=timestamp,
        filing_date=filed_date,
        period_end=period_end,
        raw_identifier=identifier,
    )
    return FilingDocument(
        identifier,
        Ticker("AAA"),
        "0000000001",
        f"0000000001-25-{identifier[-1]}",
        FilingForm.FORM_10_Q,
        datetime.combine(filed_date, datetime.min.time(), tzinfo=UTC),
        timestamp,
        period_end,
        f"{identifier}.htm",
        f"https://example.invalid/{identifier}.htm",
        content_hash,
        datetime(2025, 6, 1, tzinfo=UTC),
        mime,
        128,
        provenance,
    )


def _submissions(*, filed: str, accepted: str, period: str) -> bytes:
    recent = {
        "accessionNumber": ["0000123456-25-000001"],
        "filingDate": [filed],
        "acceptanceDateTime": [accepted],
        "reportDate": [period],
        "form": ["10-Q"],
        "primaryDocument": ["quarterly.htm"],
    }
    return json.dumps({"filings": {"recent": recent}}).encode("utf-8")


def test_parser_rejects_unclosed_active_markup_instead_of_exposing_script_text() -> None:
    content = (
        b"<html><script>Item 1A Risk Factors\npassword=secret\n"
        b"<h1>Item 1A Risk Factors</h1><p>Visible evidence</p>"
    )
    sections = SafeFilingParser().parse(_filing(), content)

    # An unclosed active element is hostile input.  Its contents must not be
    # promoted to filing evidence or section headings.
    assert all("password=secret" not in section.normalized_text for section in sections)
    assert all("Item 1A Risk Factors" not in section.normalized_text for section in sections)


def test_parser_neutralizes_style_iframe_entities_and_controls() -> None:
    content = (
        b"<style>Item 1A Risk Factors\nsteal()</style>"
        b"<iframe>Item 7 MD&amp;A</iframe>"
        b"<h1>Item 1A Risk Factors</h1><p>Safe &amp; sound &#x1b; text</p>"
    )
    sections = SafeFilingParser().parse(_filing(), content)
    assert len(sections) == 1
    assert sections[0].kind is FilingSectionKind.RISK_FACTORS
    assert "steal" not in sections[0].normalized_text
    assert "iframe" not in sections[0].normalized_text
    assert "&" in sections[0].normalized_text
    assert "\x1b" not in sections[0].normalized_text


@pytest.mark.parametrize("mime", ["application/pdf", "application/octet-stream", "image/svg+xml"])
def test_parser_unsupported_mime_fails_closed(mime: str) -> None:
    with pytest.raises(ValueError, match="unsupported filing MIME"):
        SafeFilingParser().parse(_filing(mime=mime), b"Item 1A Risk Factors\ntext")


def test_parser_byte_and_normalized_text_limits_fail_closed() -> None:
    filing = _filing("limits")
    with pytest.raises(ValueError, match="byte limit"):
        SafeFilingParser(ParseLimits(max_bytes=8)).parse(filing, b"Item 1A Risk Factors")
    with pytest.raises(ValueError, match="character limit"):
        SafeFilingParser(ParseLimits(max_text_characters=4)).parse(
            replace(filing, mime_type="text/plain"), b"Item 1A Risk Factors\ntext"
        )


def test_duplicate_and_toc_headings_are_retained_and_not_silently_collapsed() -> None:
    content = (
        b"Item 1. Business\nTable of contents\n"
        b"Item 1. Business\nActual operations\n"
        b"Item 7. Management's Discussion and Analysis\nResults"
    )
    parser = SafeFilingParser()
    sections = parser.parse(replace(_filing("toc"), mime_type="text/plain"), content)
    assert len(sections) == 3
    assert parser.diagnostics
    assert all(section.metadata["duplicate_heading"] for section in sections[:2])
    assert [section.ordinal for section in sections] == [0, 1, 2]


def test_claim_rejects_cross_filing_and_tampered_excerpt_or_span() -> None:
    filing = replace(_filing("claim"), mime_type="text/plain")
    section = SafeFilingParser().parse(filing, b"Item 1A Risk Factors\nLiquidity risk disclosed")[0]
    excerpt = "Liquidity risk"
    start = section.normalized_text.index(excerpt)
    reference = FilingEvidenceReference(
        filing.id,
        section.id,
        section.source_start + start,
        section.source_start + start + len(excerpt),
        normalized_excerpt_hash(excerpt),
    )
    claim = build_analyst_authored_claim(
        filing,
        (section,),
        as_of=date(2025, 5, 2),
        category=ClaimCategory.RISK_FACTOR,
        direction=ClaimDirection.NEGATIVE,
        statement="A disclosed risk exists.",
        evidence=(reference,),
        created_at=datetime(2025, 5, 3, tzinfo=UTC),
    )
    assert claim.source_references == (reference,)
    with pytest.raises(ValueError, match="hash|outside"):
        build_analyst_authored_claim(
            filing,
            (replace(section, normalized_text="tampered text"),),
            as_of=date(2025, 5, 2),
            category=ClaimCategory.RISK_FACTOR,
            direction=ClaimDirection.NEGATIVE,
            statement="Tampered.",
            evidence=(reference,),
            created_at=datetime(2025, 5, 3, tzinfo=UTC),
        )
    with pytest.raises(ValueError, match="cross filing|unknown"):
        build_analyst_authored_claim(
            filing,
            (replace(section, filing_id="other-filing"),),
            as_of=date(2025, 5, 2),
            category=ClaimCategory.RISK_FACTOR,
            direction=ClaimDirection.NEGATIVE,
            statement="Cross filing.",
            evidence=(reference,),
            created_at=datetime(2025, 5, 3, tzinfo=UTC),
        )


def test_disclosed_claim_is_deterministic_and_future_filing_is_invisible() -> None:
    filing = replace(_filing("risk"), mime_type="text/plain")
    section = SafeFilingParser().parse(filing, b"Item 1A Risk Factors\nLiquidity risk")[0]
    pattern = DisclosedRiskPattern("liquidity", "Liquidity risk")
    first = build_disclosed_risk_claims(
        filing, (section,), as_of=date(2025, 5, 2), patterns=(pattern,),
        created_at=datetime(2025, 5, 3, tzinfo=UTC),
    )
    second = build_disclosed_risk_claims(
        filing, (section,), as_of=date(2025, 5, 2), patterns=(pattern,),
        created_at=datetime(2025, 5, 3, tzinfo=UTC),
    )
    assert first == second
    future = replace(filing, id="future", available_at=datetime(2025, 5, 3, tzinfo=UTC))
    future_section = replace(section, filing_id="future", id="future-section")
    with pytest.raises(ValueError, match="not publicly available"):
        build_disclosed_risk_claims(
            future, (future_section,), as_of=date(2025, 5, 2), patterns=(pattern,),
            created_at=datetime(2025, 5, 3, tzinfo=UTC),
        )


def test_sec_visibility_uses_public_acceptance_not_period_end_or_filing_date() -> None:
    content = b"plain filing text"

    def transport(url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
        body = _submissions(filed="2025-05-02", accepted="2025-05-03T00:01:00Z", period="2024-03-31")
        return HttpResponse(body if "submissions" in url else content, 200)

    provider = SecFilingsProvider(
        user_agent="e2-adversarial test@example.com",
        ticker_map={"AAA": "1"},
        transport=transport,
        clock=lambda: datetime(2025, 6, 1, tzinfo=UTC),
        retries=0,
    )
    assert tuple(provider.filings(Ticker("AAA"), date(2025, 5, 2))) == ()
    visible = tuple(provider.filings(Ticker("AAA"), date(2025, 5, 3)))
    assert len(visible) == 1
    assert visible[0].period_end == date(2024, 3, 31)
    assert visible[0].available_at == datetime(2025, 5, 3, 0, 1, tzinfo=UTC)


def test_sec_rejects_oversize_mime_binary_and_unsafe_primary_document() -> None:
    valid_content = b"plain filing text"

    def transport(url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
        body = _submissions(filed="2025-05-02", accepted="2025-05-02T16:00:00Z", period="2024-03-31")
        return HttpResponse(body if "submissions" in url else valid_content, 200)

    provider = SecFilingsProvider(
        user_agent="e2-adversarial test@example.com",
        ticker_map={"AAA": "1"}, transport=transport, retries=0, max_content_bytes=3,
    )
    with pytest.raises(SecFilingProviderError, match="exceeds"):
        tuple(provider.filings(Ticker("AAA"), date(2025, 5, 2)))

    def unsafe_transport(url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
        body = _submissions(filed="2025-05-02", accepted="2025-05-02T16:00:00Z", period="2024-03-31")
        if "submissions" in url:
            payload = json.loads(body)
            payload["filings"]["recent"]["primaryDocument"] = ["../secret.htm"]
            body = json.dumps(payload).encode()
        return HttpResponse(body if "submissions" in url else valid_content, 200)

    unsafe = SecFilingsProvider(
        user_agent="e2-adversarial test@example.com", ticker_map={"AAA": "1"},
        transport=unsafe_transport, retries=0,
    )
    with pytest.raises(Exception, match="unsafe path"):
        tuple(unsafe.filings(Ticker("AAA"), date(2025, 5, 2)))


def test_sec_content_hash_tampering_is_rejected() -> None:
    content = b"plain filing text"

    def transport(url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
        body = _submissions(filed="2025-05-02", accepted="2025-05-02T16:00:00Z", period="2024-03-31")
        return HttpResponse(body if "submissions" in url else content, 200)

    provider = SecFilingsProvider(
        user_agent="e2-adversarial test@example.com", ticker_map={"AAA": "1"},
        transport=transport, retries=0,
    )
    filing = next(iter(provider.filings(Ticker("AAA"), date(2025, 5, 2))))
    with pytest.raises(SecFilingProviderError, match="content changed"):
        provider.content(replace(filing, content_hash=hashlib.sha256(b"tampered").hexdigest()))


def test_history_is_identity_safe_under_reordering_and_asymmetric_sections() -> None:
    before = replace(_filing("before"), available_at=datetime(2025, 5, 2, tzinfo=UTC))
    after = replace(_filing("after"), available_at=datetime(2025, 5, 30, tzinfo=UTC))
    parser = SafeFilingParser()
    old = parser.parse(replace(before, mime_type="text/plain"), b"Item 1. Business\nOld business\nItem 1A. Risk Factors\nOld risk")
    new = parser.parse(replace(after, mime_type="text/plain"), b"Item 1A. Risk Factors\nNew risk\nItem 7. Management's Discussion and Analysis\nNew MD&A")
    first = FilingHistoryComparator().compare(before, old, after, new)
    second = FilingHistoryComparator().compare(before, tuple(reversed(old)), after, tuple(reversed(new)))
    assert first == second
    assert {change.change_type.value for change in first} == {"section_removed", "section_added", "section_modified"}
    assert all(change.ticker == Ticker("AAA") for change in first)


def test_sqlite_filing_evidence_is_immutable_and_survives_close_reopen(tmp_path: object) -> None:
    path = tmp_path / "filings.sqlite"  # type: ignore[union-attr]
    filing = replace(_filing("stored"), mime_type="text/plain")
    content = b"Item 1A Risk Factors\nLiquidity risk"
    section = SafeFilingParser().parse(filing, content)[0]
    claim = build_disclosed_risk_claims(
        filing, (section,), as_of=date(2025, 5, 2),
        patterns=(DisclosedRiskPattern("liquidity", "Liquidity risk"),),
        created_at=datetime(2025, 5, 3, tzinfo=UTC),
    )[0]
    with SQLiteStorage(path) as storage:
        storage.save_filing_document(filing)
        storage.save_filing_section(section)
        storage.save_qualitative_claim(claim)
        with pytest.raises(ValueError, match="immutable filing_documents"):
            storage.save_filing_document(replace(filing, source_url="https://tampered.invalid"))
    with SQLiteStorage(path) as reopened:
        assert reopened.load_filing_document(filing.id) == filing
        assert reopened.load_filing_sections(filing.id) == (section,)
        assert reopened.load_qualitative_claims(filing_id=filing.id) == (claim,)
