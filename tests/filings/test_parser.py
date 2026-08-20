from datetime import date, datetime, timezone

import pytest

from stocks_investment.domain.filings import FilingDocument, FilingForm, FilingSectionKind
from stocks_investment.domain.models import DataProvenance, Ticker
from stocks_investment.filings.parser import ParseLimits, SafeFilingParser


def _filing(mime: str = "text/html") -> FilingDocument:
    now = datetime(2025, 1, 2, tzinfo=timezone.utc)
    provenance = DataProvenance(source="fixture", provider="fixture", retrieved_at=now, effective_date=date(2025, 1, 2))
    return FilingDocument("f1", Ticker("AAA"), "0000000001", "0001-25-000001", FilingForm.FORM_10_K, now, now, date(2024, 12, 31), "a.htm", "https://example.invalid/a.htm", "x", now, mime, 1, provenance)


def test_removes_active_markup_and_extracts_sections() -> None:
    content = b"<html><script>alert(1)</script><h1>Item 1A - Risk Factors</h1><p>Safe &amp; sound</p><h1>Item 7 MD&amp;A</h1><p>Results</p></html>"
    sections = SafeFilingParser().parse(_filing(), content)
    assert [section.kind for section in sections] == [FilingSectionKind.RISK_FACTORS, FilingSectionKind.MD_AND_A]
    assert "alert" not in sections[0].normalized_text
    assert "&" in sections[0].normalized_text


def test_heading_variants_duplicate_headings_and_deterministic_hash() -> None:
    content = b"Item 1. Business\nTOC\nItem 1. Business\nActual operations\nItem 9A. Controls and Procedures\nControl text"
    first = SafeFilingParser()
    second = SafeFilingParser()
    left = first.parse(_filing("text/plain"), content)
    right = second.parse(_filing("text/plain"), content)
    assert len(left) == 3
    assert left == right
    assert all(section.metadata["duplicate_heading"] for section in left[:2])
    assert first.diagnostics
    assert left[0].content_hash == left[0].content_hash


def test_malformed_html_and_control_characters_are_inert() -> None:
    sections = SafeFilingParser().parse(_filing(), b"<div><h2>Item 1A Risk Factors<h2><p>Bad\x00\x1b[2J text")
    assert sections
    assert "\x1b" not in sections[0].normalized_text
    assert "Bad" in sections[0].normalized_text


def test_limits_and_unsupported_mime_fail_closed() -> None:
    with pytest.raises(ValueError, match="byte limit"):
        SafeFilingParser(ParseLimits(max_bytes=3)).parse(_filing(), b"abcd")
    with pytest.raises(ValueError, match="unsupported"):
        SafeFilingParser().parse(_filing("application/pdf"), b"data")


def test_no_external_access_and_offsets_are_byte_offsets() -> None:
    content = "<a href='http://127.0.0.1/secret'>Item 1A Risk Factors</a><p>Evidence</p>".encode()
    sections = SafeFilingParser().parse(_filing(), content)
    assert sections[0].source_start < sections[0].source_end <= len(content)
    assert "http://" not in sections[0].normalized_text


def test_too_many_sections_rejected() -> None:
    content = ("\n".join("Item 1A Risk Factors\ntext" for _ in range(3))).encode()
    with pytest.raises(ValueError, match="section count"):
        SafeFilingParser(ParseLimits(max_sections=2)).parse(_filing("text/plain"), content)
