from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path

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
from stocks_investment.storage import SQLiteStorage


def _filing(identifier: str, accession: str, available: datetime) -> FilingDocument:
    provenance = DataProvenance(
        "sec:archive", "sec-edgar", available, available.date(), available_at=available,
        filing_date=available.date(), period_end=date(2024, 12, 31), raw_identifier=accession,
    )
    return FilingDocument(
        identifier, Ticker("AAA"), "0000000001", accession, FilingForm.FORM_10_K,
        available, available, date(2024, 12, 31), "report.htm",
        f"https://www.sec.gov/Archives/{accession}", f"sha256:{identifier}", available,
        "text/html", 1000, provenance,
    )


def test_wave_e2_evidence_is_immutable_and_round_trips(tmp_path: Path) -> None:
    old = _filing("filing-old", "0001-old", datetime(2024, 2, 1, tzinfo=timezone.utc))
    current = _filing("filing-new", "0001-new", datetime(2025, 2, 1, tzinfo=timezone.utc))
    section = FilingSection(
        "section-new", current.id, "1A", "Risk Factors", FilingSectionKind.RISK_FACTORS,
        1, "Demand concentration may adversely affect results.", "sha256:section", 10, 61,
        "sec_html_sections_v1", {"safe_html": True},
    )
    reference = FilingEvidenceReference(current.id, section.id, 0, 20, "sha256:excerpt")
    claim = QualitativeClaim(
        "claim-new", Ticker("AAA"), current.available_at.date(), current.id, "claims_v1",
        ClaimCategory.RISK_FACTOR, ClaimDirection.NEGATIVE, "Demand concentration is disclosed.",
        ClaimStatus.SUPPORTED, ClaimMethod.DETERMINISTIC, (reference,), current.available_at,
    )
    change = FilingSectionChange(
        "change-new", Ticker("AAA"), old.id, current.id, "section-old", section.id,
        FilingChangeType.SECTION_MODIFIED, "filing_diff_v1", 0.5, True,
        "risk section changed", (reference,),
    )
    snapshot = FilingEvidenceSnapshot(
        "filing-snapshot", Ticker("AAA"), current.available_at.date(), (old.id, current.id),
        (section.id,), (claim.id,), "filing_snapshot_v1", current.available_at,
    )
    path = tmp_path / "filings.db"
    with SQLiteStorage(path) as storage:
        storage.save_filing_document(old)
        storage.save_filing_document(current)
        storage.save_filing_section(section)
        storage.save_qualitative_claim(claim)
        storage.save_filing_section_change(change)
        storage.save_filing_evidence_snapshot(snapshot)
        with pytest.raises(ValueError, match="immutable filing_sections"):
            storage.save_filing_section(replace(section, normalized_text="rewritten history"))

    with SQLiteStorage(path) as reopened:
        assert reopened.load_filing_document(current.id) == current
        assert reopened.load_filings_available_on(Ticker("AAA"), date(2024, 12, 31)) == (old,)
        assert reopened.load_filing_sections(current.id) == (section,)
        assert reopened.load_qualitative_claims(filing_id=current.id) == (claim,)
        assert reopened.load_filing_section_changes(Ticker("AAA")) == (change,)
        assert reopened.load_filing_evidence_snapshot(snapshot.id) == snapshot
