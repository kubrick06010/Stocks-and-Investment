from datetime import date, datetime, timezone

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


FILED = datetime(2025, 2, 14, 21, 1, tzinfo=timezone.utc)


def _filing(identifier: str = "filing-1", available: datetime = FILED) -> FilingDocument:
    provenance = DataProvenance(
        "sec:archive", "sec-edgar", available, available.date(), available_at=available,
        filing_date=available.date(), period_end=date(2024, 12, 31),
        raw_identifier="0001/2025/10-k.htm",
    )
    return FilingDocument(
        identifier, Ticker("AAA"), "0000000001", "0001-25-000001", FilingForm.FORM_10_K,
        FILED, available, date(2024, 12, 31), "annual-report.htm",
        "https://www.sec.gov/Archives/example", "sha256:document", available,
        "text/html", 1024, provenance,
    )


def _section(filing_id: str = "filing-1") -> FilingSection:
    return FilingSection(
        "section-risk", filing_id, "1A", "Risk Factors", FilingSectionKind.RISK_FACTORS,
        1, "Demand concentration may adversely affect results.", "sha256:section", 100, 151,
        "sec_html_sections_v1",
    )


def test_filing_availability_is_distinct_from_period_end_and_retrieval() -> None:
    filing = _filing()
    assert filing.period_end == date(2024, 12, 31)
    assert not filing.is_available_on(date(2025, 2, 13))
    assert filing.is_available_on(date(2025, 2, 14))


def test_filing_cannot_be_available_before_acceptance() -> None:
    with pytest.raises(ValueError, match="available before"):
        _filing(available=datetime(2025, 2, 13, tzinfo=timezone.utc))


def test_supported_claim_requires_exact_filing_evidence() -> None:
    section = _section()
    reference = FilingEvidenceReference("filing-1", section.id, 0, 20, "sha256:excerpt")
    claim = QualitativeClaim(
        "claim-1", Ticker("AAA"), date(2025, 2, 14), "filing-1", "claims_v1",
        ClaimCategory.RISK_FACTOR, ClaimDirection.NEGATIVE, "Demand concentration is disclosed.",
        ClaimStatus.SUPPORTED, ClaimMethod.DETERMINISTIC, (reference,), FILED,
    )
    assert claim.source_references == (reference,)
    with pytest.raises(ValueError, match="require filing evidence"):
        QualitativeClaim(
            "claim-2", Ticker("AAA"), date(2025, 2, 14), "filing-1", "claims_v1",
            ClaimCategory.RISK_FACTOR, ClaimDirection.NEGATIVE, "Unsupported",
            ClaimStatus.SUPPORTED, ClaimMethod.DETERMINISTIC, (), FILED,
        )


def test_claim_evidence_cannot_cross_filing_identity() -> None:
    reference = FilingEvidenceReference("filing-2", "section-risk", 0, 10, "sha256:x")
    with pytest.raises(ValueError, match="referenced filing"):
        QualitativeClaim(
            "claim", Ticker("AAA"), date(2025, 2, 14), "filing-1", "claims_v1",
            ClaimCategory.RISK_FACTOR, ClaimDirection.NEGATIVE, "Mismatch",
            ClaimStatus.SUPPORTED, ClaimMethod.ANALYST_AUTHORED, (reference,), FILED,
        )


def test_section_change_preserves_both_historical_sources() -> None:
    change = FilingSectionChange(
        "change-1", Ticker("AAA"), "filing-0", "filing-1", "risk-old", "risk-new",
        FilingChangeType.SECTION_MODIFIED, "filing_diff_v1", 0.72, True,
        "risk section text changed materially",
    )
    assert change.from_filing_id != change.to_filing_id
    assert change.similarity == 0.72


def test_snapshot_freezes_exact_filing_section_and_claim_ids() -> None:
    snapshot = FilingEvidenceSnapshot(
        "snapshot-1", Ticker("AAA"), date(2025, 2, 14), ("filing-1",),
        ("section-risk",), ("claim-1",), "filing_snapshot_v1", FILED,
    )
    assert snapshot.filing_ids == ("filing-1",)
    assert snapshot.methodology_version == "filing_snapshot_v1"
