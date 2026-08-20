from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import json

import pytest

from stocks_investment.domain import (
    ClaimCategory,
    ClaimDirection,
    ClaimMethod,
    ClaimStatus,
    DataProvenance,
    FilingChangeType,
    FilingDocument,
    FilingEvidenceReference,
    FilingEvidenceSnapshot,
    FilingForm,
    FilingSection,
    FilingSectionChange,
    FilingSectionKind,
    QualitativeClaim,
    Ticker,
)
from stocks_investment.filings.claims import normalized_excerpt_hash
from stocks_investment.reporting.builder import render_json, render_markdown
from stocks_investment.reporting.filings import (
    build_filing_evidence_report,
    build_filing_history_report,
)


AVAILABLE = datetime(2025, 2, 14, 21, 1, tzinfo=timezone.utc)


def _filing(identifier: str, *, available: datetime = AVAILABLE) -> FilingDocument:
    provenance = DataProvenance(
        "sec:archive", "sec-edgar", available, available.date(), available_at=available,
        filing_date=available.date(), period_end=date(2024, 12, 31),
        raw_identifier=f"0001/{identifier}.htm",
    )
    return FilingDocument(
        identifier, Ticker("AAA"), "0000000001", f"0001-{identifier}", FilingForm.FORM_10_K,
        available, available, date(2024, 12, 31), "annual-report.htm",
        f"https://www.sec.gov/Archives/{identifier}", f"sha256:{identifier}", available,
        "text/html", 1024, provenance,
    )


def _section(filing_id: str, identifier: str, text: str = "Liquidity risk is disclosed.") -> FilingSection:
    return FilingSection(
        identifier, filing_id, "1A", "Risk Factors", FilingSectionKind.RISK_FACTORS,
        0, text, f"sha256:{identifier}", 0, len(text), "sec_html_sections_v1",
    )


def _claim(filing: FilingDocument, section: FilingSection, *, status: ClaimStatus = ClaimStatus.SUPPORTED) -> QualitativeClaim:
    excerpt = section.normalized_text[:10]
    reference = FilingEvidenceReference(
        filing.id, section.id, 0, len(excerpt), normalized_excerpt_hash(excerpt),
    )
    return QualitativeClaim(
        f"claim-{filing.id}", filing.ticker, filing.available_at.date(), filing.id,
        "filing_claims_v1", ClaimCategory.RISK_FACTOR, ClaimDirection.NEGATIVE,
        "Liquidity risk is disclosed.", status, ClaimMethod.DETERMINISTIC,
        (reference,) if status is ClaimStatus.SUPPORTED else (), filing.available_at,
    )


def _change(previous: FilingDocument, current: FilingDocument, before: FilingSection, after: FilingSection) -> FilingSectionChange:
    return FilingSectionChange(
        "change-1", previous.ticker, previous.id, current.id, before.id, after.id,
        FilingChangeType.SECTION_MODIFIED, "filing_diff_v1", 0.5, True,
        "risk disclosure changed materially",
    )


def test_evidence_report_preserves_lineage_and_uses_generic_renderers() -> None:
    filing = _filing("f1")
    section = _section(filing.id, "s1")
    claim = _claim(filing, section)
    snapshot = FilingEvidenceSnapshot(
        "snapshot-1", filing.ticker, filing.available_at.date(),
        (filing.id,), (section.id,), (claim.id,), "filing_snapshot_v1", AVAILABLE,
    )

    report = build_filing_evidence_report(filing, (section,), (claim,), snapshot=snapshot)
    encoded = json.loads(render_json(report))
    markdown = render_markdown(report)

    assert report.report_type == "filing_evidence"
    assert report.sections[0].section_type == "evidence"
    assert report.sections[1].section_type == "interpretation"
    assert "sha256:s1" in render_json(report)
    assert "sec_html_sections_v1" in render_json(report)
    assert "filing_claims_v1" in render_json(report)
    assert encoded["sections"][0]["source_references"]
    assert "# filing_evidence" in markdown


def test_empty_and_unsupported_claims_are_explicit() -> None:
    filing = _filing("f1")
    section = _section(filing.id, "s1")
    empty = build_filing_evidence_report(filing, (section,))
    unsupported = build_filing_evidence_report(
        filing, (section,), (_claim(filing, section, status=ClaimStatus.INSUFFICIENT_EVIDENCE),)
    )

    assert empty.sections[1].payload["empty_claims"] is True
    claims = unsupported.sections[1].payload["claims"]
    assert claims[0]["status"] == "insufficient_evidence"
    assert claims[0]["methodology_version"] == "filing_claims_v1"


def test_report_escapes_active_html_but_keeps_content_hash() -> None:
    filing = _filing("f1")
    section = _section(filing.id, "s1", "<script>alert('x')</script> liquidity risk")
    report = build_filing_evidence_report(filing, (section,))
    encoded = render_json(report)
    markdown = render_markdown(report)

    assert "<script>" not in encoded
    assert "<script>" not in markdown
    assert "&lt;script&gt;" in encoded
    assert "sha256:s1" in encoded


def test_history_report_separates_evidence_interpretation_and_later_changes() -> None:
    previous = _filing("f0")
    current = _filing("f1", available=datetime(2025, 5, 2, 21, 1, tzinfo=timezone.utc))
    before = _section(previous.id, "s0", "Stable liquidity disclosure.")
    after = _section(current.id, "s1", "Material liquidity disclosure changed.")
    change = _change(previous, current, before, after)
    report = build_filing_history_report(previous, (before,), current, (after,), (change,))

    types = [item.section_type for item in report.sections]
    assert types == ["evidence", "interpretation", "history"]
    assert report.metadata["later_changes_are_not_prior_knowledge"] is True
    assert "filing_diff_v1" in render_json(report)
    assert "filing_section_change:change-1" in render_markdown(report)


def test_history_rejects_future_as_of_and_cross_filing_inputs() -> None:
    previous = _filing("f0")
    current = _filing("f1", available=datetime(2025, 5, 2, 21, 1, tzinfo=timezone.utc))
    before = _section(previous.id, "s0")
    after = _section(current.id, "s1")

    with pytest.raises(ValueError, match="not publicly available"):
        build_filing_evidence_report(current, (after,), as_of=date(2025, 4, 30))
    with pytest.raises(ValueError, match="match the reported filing pair"):
        build_filing_history_report(previous, (before,), current, (after,), (
            _change(previous, _filing("f2"), before, _section("f2", "s2")),
        ))


def test_claim_authored_after_filing_is_visible_only_on_or_after_claim_date() -> None:
    filing = _filing("f1")
    section = _section(filing.id, "s1")
    claim = replace(_claim(filing, section), as_of=filing.available_at.date() + timedelta(days=2))

    with pytest.raises(ValueError, match="information set"):
        build_filing_evidence_report(
            filing, (section,), (claim,), as_of=filing.available_at.date()
        )
    report = build_filing_evidence_report(filing, (section,), (claim,), as_of=claim.as_of)
    assert report.sections[1].payload["claims"]
