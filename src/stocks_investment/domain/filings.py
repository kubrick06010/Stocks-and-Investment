"""Immutable evidence-first contracts for qualitative filing intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Mapping

from .models import DataProvenance, Ticker


class FilingForm(StrEnum):
    FORM_10_K = "10-K"
    FORM_10_K_A = "10-K/A"
    FORM_10_Q = "10-Q"
    FORM_10_Q_A = "10-Q/A"
    FORM_8_K = "8-K"
    FORM_8_K_A = "8-K/A"


class FilingSectionKind(StrEnum):
    BUSINESS = "business"
    RISK_FACTORS = "risk_factors"
    MD_AND_A = "management_discussion_and_analysis"
    MARKET_RISK = "market_risk"
    FINANCIAL_STATEMENTS = "financial_statements"
    CONTROLS = "controls_and_procedures"
    OTHER = "other"


class ClaimCategory(StrEnum):
    BUSINESS_MODEL = "business_model"
    RISK_FACTOR = "risk_factor"
    GUIDANCE = "guidance"
    CAPITAL_ALLOCATION = "capital_allocation"
    COMPETITIVE_POSITION = "competitive_position"
    ACCOUNTING_POLICY = "accounting_policy"
    MATERIAL_EVENT = "material_event"


class ClaimDirection(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class ClaimStatus(StrEnum):
    SUPPORTED = "supported"
    CONTESTED = "contested"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    RETRACTED = "retracted"


class ClaimMethod(StrEnum):
    DETERMINISTIC = "deterministic"
    ANALYST_AUTHORED = "analyst_authored"


class FilingChangeType(StrEnum):
    SECTION_ADDED = "section_added"
    SECTION_REMOVED = "section_removed"
    SECTION_MODIFIED = "section_modified"
    SECTION_UNCHANGED = "section_unchanged"


@dataclass(frozen=True, slots=True)
class FilingDocument:
    id: str
    ticker: Ticker
    cik: str
    accession_number: str
    form: FilingForm
    filed_at: datetime
    available_at: datetime
    period_end: date | None
    primary_document: str
    source_url: str
    content_hash: str
    retrieved_at: datetime
    mime_type: str
    size_bytes: int
    provenance: DataProvenance

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.id,
                self.cik,
                self.accession_number,
                self.primary_document,
                self.source_url,
                self.content_hash,
                self.mime_type,
            )
        ):
            raise ValueError("filing identity, source and content hash are required")
        if self.size_bytes <= 0:
            raise ValueError("filing size must be positive")
        if self.available_at < self.filed_at:
            raise ValueError("filing cannot be available before it was filed")
        if self.retrieved_at < self.available_at:
            raise ValueError("filing cannot be retrieved before public availability")
        if not self.provenance.is_available_on(self.available_at.date()):
            raise ValueError("filing provenance conflicts with availability")

    def is_available_on(self, as_of: date) -> bool:
        return self.available_at.date() <= as_of


@dataclass(frozen=True, slots=True)
class FilingSection:
    id: str
    filing_id: str
    item: str
    title: str
    kind: FilingSectionKind
    ordinal: int
    normalized_text: str
    content_hash: str
    source_start: int
    source_end: int
    parser_version: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.filing_id or not self.item or not self.content_hash:
            raise ValueError("section identity and content hash are required")
        if self.ordinal < 0 or self.source_start < 0 or self.source_end <= self.source_start:
            raise ValueError("invalid filing section position")
        if not self.normalized_text.strip() or not self.parser_version:
            raise ValueError("section text and parser version are required")


@dataclass(frozen=True, slots=True)
class FilingEvidenceReference:
    filing_id: str
    section_id: str
    source_start: int
    source_end: int
    excerpt_hash: str

    def __post_init__(self) -> None:
        if not self.filing_id or not self.section_id or not self.excerpt_hash:
            raise ValueError("evidence source identity is required")
        if self.source_start < 0 or self.source_end <= self.source_start:
            raise ValueError("invalid evidence span")


@dataclass(frozen=True, slots=True)
class QualitativeClaim:
    id: str
    ticker: Ticker
    as_of: date
    filing_id: str
    methodology_version: str
    category: ClaimCategory
    direction: ClaimDirection
    statement: str
    status: ClaimStatus
    method: ClaimMethod
    source_references: tuple[FilingEvidenceReference, ...]
    created_at: datetime
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.filing_id or not self.methodology_version or not self.statement.strip():
            raise ValueError("claim identity, methodology and statement are required")
        if self.status is ClaimStatus.SUPPORTED and not self.source_references:
            raise ValueError("supported qualitative claims require filing evidence")
        if any(reference.filing_id != self.filing_id for reference in self.source_references):
            raise ValueError("claim evidence must belong to the referenced filing")


@dataclass(frozen=True, slots=True)
class FilingSectionChange:
    id: str
    ticker: Ticker
    from_filing_id: str
    to_filing_id: str
    from_section_id: str | None
    to_section_id: str | None
    change_type: FilingChangeType
    methodology_version: str
    similarity: float | None
    material: bool
    rationale: str
    source_references: tuple[FilingEvidenceReference, ...] = ()

    def __post_init__(self) -> None:
        if not self.id or not self.from_filing_id or not self.to_filing_id or not self.methodology_version:
            raise ValueError("filing change identity and methodology are required")
        if self.from_filing_id == self.to_filing_id:
            raise ValueError("filing change requires two different filings")
        if self.similarity is not None and not 0 <= self.similarity <= 1:
            raise ValueError("section similarity must be in 0..1")
        if self.change_type is FilingChangeType.SECTION_ADDED and self.to_section_id is None:
            raise ValueError("added section requires a destination section")
        if self.change_type is FilingChangeType.SECTION_REMOVED and self.from_section_id is None:
            raise ValueError("removed section requires a source section")


@dataclass(frozen=True, slots=True)
class FilingEvidenceSnapshot:
    id: str
    ticker: Ticker
    as_of: date
    filing_ids: tuple[str, ...]
    section_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]
    methodology_version: str
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.id or not self.methodology_version:
            raise ValueError("filing evidence snapshot identity is required")
        if not self.filing_ids:
            raise ValueError("filing evidence snapshot requires at least one filing")
