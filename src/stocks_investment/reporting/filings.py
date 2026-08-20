"""Evidence-first reports for persisted SEC filing artifacts.

This module only assembles already persisted objects.  It does not parse filing
content, call providers, or infer a thesis.  The generic report renderers are
intentionally kept at the edge; the payloads below preserve the evidence and
its lineage for JSON, Markdown, or another future adapter.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from html import escape
from typing import Iterable, Sequence

from stocks_investment.domain.filings import (
    FilingDocument,
    FilingEvidenceSnapshot,
    FilingSection,
    FilingSectionChange,
    QualitativeClaim,
)
from stocks_investment.domain.research_intelligence import ReportSection, ResearchReport, SourceReference
from stocks_investment.reporting.builder import build_report


def build_filing_evidence_report(
    filing: FilingDocument,
    sections: Iterable[FilingSection],
    claims: Iterable[QualitativeClaim] = (),
    *,
    snapshot: FilingEvidenceSnapshot | None = None,
    as_of: date | None = None,
) -> ResearchReport:
    """Build a point-in-time filing evidence report from persisted artifacts."""

    selected_sections = _validate_sections(filing, sections)
    report_date = as_of or filing.available_at.date()
    _validate_as_of(filing, report_date)
    selected_claims = _validate_claims(filing, claims, report_date)
    _validate_snapshot(snapshot, filing, selected_sections, selected_claims, report_date)

    evidence_refs = (SourceReference("filing_document", filing.id),) + tuple(
        SourceReference("filing_section", section.id, section.content_hash)
        for section in selected_sections
    )
    claim_refs = tuple(
        SourceReference("qualitative_claim", claim.id, claim.methodology_version)
        for claim in selected_claims
    )
    snapshot_refs = (SourceReference("filing_evidence_snapshot", snapshot.id),) if snapshot else ()

    sections_out = (
        ReportSection(
            "FILING EVIDENCE",
            "evidence",
            {
                "ticker": filing.ticker.symbol,
                "as_of": report_date,
                "filing": _document_payload(filing),
                "sections": tuple(_section_payload(section) for section in selected_sections),
                "boundary": "raw persisted filing evidence available at as_of",
            },
            evidence_refs + snapshot_refs,
        ),
        ReportSection(
            "DETERMINISTIC CLAIMS",
            "interpretation",
            {
                "claims": tuple(_claim_payload(claim) for claim in selected_claims),
                "empty_claims": not selected_claims,
                "boundary": "claims are interpretations of the cited filing evidence; they are not a thesis or outcome",
            },
            claim_refs,
        ),
    )
    source_ids = (filing.id,) + ((snapshot.id,) if snapshot else ())
    return build_report(
        "filing_evidence",
        report_date,
        source_ids,
        sections_out,
        metadata={
            "ticker": filing.ticker.symbol,
            "information_boundary": "evidence_then_deterministic_interpretation",
            "filing_content_hash": filing.content_hash,
            "claim_methodology_versions": tuple(sorted({claim.methodology_version for claim in selected_claims})),
        },
    )


def build_filing_history_report(
    previous_filing: FilingDocument,
    previous_sections: Iterable[FilingSection],
    current_filing: FilingDocument,
    current_sections: Iterable[FilingSection],
    changes: Iterable[FilingSectionChange],
    claims: Iterable[QualitativeClaim] = (),
    *,
    as_of: date | None = None,
) -> ResearchReport:
    """Build a report comparing two persisted filing states by section identity."""

    previous = _validate_sections(previous_filing, previous_sections)
    current = _validate_sections(current_filing, current_sections)
    if previous_filing.ticker != current_filing.ticker:
        raise ValueError("filing history requires the same ticker")
    if current_filing.available_at < previous_filing.available_at:
        raise ValueError("filing history cannot move from future to past")
    report_date = as_of or current_filing.available_at.date()
    _validate_as_of(current_filing, report_date)
    if not previous_filing.is_available_on(report_date):
        raise ValueError("previous filing is not available at the report as-of date")

    selected_changes = tuple(sorted(changes, key=lambda item: item.id))
    _validate_changes(selected_changes, previous_filing, current_filing, report_date)
    selected_claims = _validate_claims(current_filing, claims, report_date)
    evidence_refs = tuple(
        [SourceReference("filing_document", current_filing.id)]
        + [SourceReference("filing_section", item.id, item.content_hash) for item in current]
        + [SourceReference("filing_document", previous_filing.id)]
        + [SourceReference("filing_section", item.id, item.content_hash) for item in previous]
    )
    change_refs = tuple(
        SourceReference("filing_section_change", item.id, item.methodology_version)
        for item in selected_changes
    )
    claim_refs = tuple(
        SourceReference("qualitative_claim", item.id, item.methodology_version)
        for item in selected_claims
    )
    report_sections = (
        ReportSection(
            "CURRENT FILING EVIDENCE",
            "evidence",
            {
                "as_of": report_date,
                "filing": _document_payload(current_filing),
                "sections": tuple(_section_payload(item) for item in current),
                "boundary": "raw evidence available at the current filing as_of",
            },
            evidence_refs,
        ),
        ReportSection(
            "DETERMINISTIC CLAIMS",
            "interpretation",
            {
                "claims": tuple(_claim_payload(item) for item in selected_claims),
                "empty_claims": not selected_claims,
                "boundary": "claims are filing-grounded interpretations, not future outcomes",
            },
            claim_refs,
        ),
        ReportSection(
            "FILING SECTION HISTORY",
            "history",
            {
                "previous_filing_id": previous_filing.id,
                "current_filing_id": current_filing.id,
                "changes": tuple(_change_payload(item) for item in selected_changes),
                "boundary": "a later filing change was not known when the earlier filing was published",
            },
            change_refs,
        ),
    )
    return build_report(
        "filing_history",
        report_date,
        (previous_filing.id, current_filing.id),
        report_sections,
        metadata={
            "ticker": current_filing.ticker.symbol,
            "information_boundary": "historical_evidence_then_deterministic_section_comparison",
            "comparison_methodology_versions": tuple(sorted({item.methodology_version for item in selected_changes})),
            "later_changes_are_not_prior_knowledge": True,
        },
    )


def _validate_as_of(filing: FilingDocument, as_of: date) -> None:
    if not filing.is_available_on(as_of):
        raise ValueError("filing is not publicly available at the requested as_of date")


def _validate_sections(filing: FilingDocument, sections: Iterable[FilingSection]) -> tuple[FilingSection, ...]:
    selected = tuple(sorted(sections, key=lambda item: (item.ordinal, item.id)))
    if any(item.filing_id != filing.id for item in selected):
        raise ValueError("sections cannot cross filing identity")
    if len({item.id for item in selected}) != len(selected):
        raise ValueError("duplicate filing section identity")
    return selected


def _validate_claims(
    filing: FilingDocument, claims: Iterable[QualitativeClaim], report_as_of: date
) -> tuple[QualitativeClaim, ...]:
    selected = tuple(sorted(claims, key=lambda item: item.id))
    if any(item.filing_id != filing.id or item.ticker != filing.ticker for item in selected):
        raise ValueError("claims cannot cross filing identity")
    if len({item.id for item in selected}) != len(selected):
        raise ValueError("duplicate qualitative claim identity")
    if any(not filing.is_available_on(item.as_of) or item.as_of > report_as_of for item in selected):
        raise ValueError("claim is outside the filing report information set")
    return selected


def _validate_snapshot(
    snapshot: FilingEvidenceSnapshot | None,
    filing: FilingDocument,
    sections: Sequence[FilingSection],
    claims: Sequence[QualitativeClaim],
    as_of: date,
) -> None:
    if snapshot is None:
        return
    if snapshot.ticker != filing.ticker or snapshot.as_of > as_of:
        raise ValueError("snapshot is incompatible with filing report")
    if filing.id not in snapshot.filing_ids:
        raise ValueError("snapshot does not reference the reported filing")
    if not set(section.id for section in sections).issubset(snapshot.section_ids):
        raise ValueError("snapshot does not reference every reported section")
    if not set(claim.id for claim in claims).issubset(snapshot.claim_ids):
        raise ValueError("snapshot does not reference every reported claim")


def _validate_changes(
    changes: Sequence[FilingSectionChange],
    previous: FilingDocument,
    current: FilingDocument,
    as_of: date,
) -> None:
    for change in changes:
        if change.ticker != current.ticker or change.from_filing_id != previous.id or change.to_filing_id != current.id:
            raise ValueError("filing change does not match the reported filing pair")
        if not current.is_available_on(as_of):
            raise ValueError("filing change is not available at the requested as_of date")


def _document_payload(filing: FilingDocument) -> dict[str, object]:
    payload = asdict(filing)
    payload["ticker"] = filing.ticker.symbol
    payload["form"] = filing.form.value
    payload["source_url"] = filing.source_url
    payload["provenance"] = asdict(filing.provenance)
    return payload


def _section_payload(section: FilingSection) -> dict[str, object]:
    return {
        "id": section.id,
        "filing_id": section.filing_id,
        "item": section.item,
        "title": section.title,
        "kind": section.kind.value,
        "ordinal": section.ordinal,
        "content_hash": section.content_hash,
        "parser_version": section.parser_version,
        "source_start": section.source_start,
        "source_end": section.source_end,
        "normalized_text": escape(section.normalized_text, quote=False),
        "metadata": dict(section.metadata),
        "presentation_note": "normalized text is escaped for safe report rendering; its hash is preserved",
    }


def _claim_payload(claim: QualitativeClaim) -> dict[str, object]:
    return {
        "id": claim.id,
        "ticker": claim.ticker.symbol,
        "as_of": claim.as_of,
        "filing_id": claim.filing_id,
        "methodology_version": claim.methodology_version,
        "category": claim.category.value,
        "direction": claim.direction.value,
        "statement": escape(claim.statement, quote=False),
        "status": claim.status.value,
        "method": claim.method.value,
        "source_references": tuple(asdict(item) for item in claim.source_references),
    }


def _change_payload(change: FilingSectionChange) -> dict[str, object]:
    return {
        "id": change.id,
        "ticker": change.ticker.symbol,
        "from_filing_id": change.from_filing_id,
        "to_filing_id": change.to_filing_id,
        "from_section_id": change.from_section_id,
        "to_section_id": change.to_section_id,
        "change_type": change.change_type.value,
        "methodology_version": change.methodology_version,
        "similarity": change.similarity,
        "material": change.material,
        "rationale": escape(change.rationale, quote=False),
        "source_references": tuple(asdict(item) for item in change.source_references),
    }
