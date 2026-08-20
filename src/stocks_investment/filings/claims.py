"""Deterministic, evidence-first qualitative filing claims.

This module deliberately stops short of NLP.  It constructs either an
analyst-authored claim with explicitly supplied evidence, or a narrowly
configured presence claim for a disclosed-risk pattern.  Filing text is
treated as untrusted evidence and is never interpreted as instructions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
import re
from typing import Iterable, Sequence

from stocks_investment.domain.filings import (
    ClaimCategory,
    ClaimDirection,
    ClaimMethod,
    ClaimStatus,
    FilingDocument,
    FilingEvidenceReference,
    FilingSection,
    FilingSectionKind,
    QualitativeClaim,
)


CLAIMS_ANALYST_VERSION = "filing_claims_analyst_v1"
DISCLOSED_RISK_VERSION = "filing_disclosed_risk_v1"


@dataclass(frozen=True, slots=True)
class DisclosedRiskPattern:
    """A predeclared, literal/regex-free disclosure-presence rule.

    ``pattern`` is matched as a case-insensitive literal substring by
    default.  The optional section restriction prevents a generic phrase in
    an unrelated filing section from becoming a risk claim.
    """

    name: str
    pattern: str
    section_kinds: tuple[FilingSectionKind, ...] = (FilingSectionKind.RISK_FACTORS,)
    statement: str | None = None
    case_sensitive: bool = False

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.pattern:
            raise ValueError("risk pattern name and pattern are required")
        if self.statement is not None and not self.statement.strip():
            raise ValueError("risk pattern statement cannot be blank")


def normalized_excerpt_hash(excerpt: str) -> str:
    """Return the canonical hash stored in a ``FilingEvidenceReference``."""

    return "sha256:" + hashlib.sha256(excerpt.encode("utf-8")).hexdigest()


def _hash_matches(value: str, excerpt: str) -> bool:
    digest = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
    return value.lower() in {digest, "sha256:" + digest}


def _sections_for(filing: FilingDocument, sections: Iterable[FilingSection]) -> tuple[FilingSection, ...]:
    selected = tuple(sections)
    if not selected:
        raise ValueError("at least one filing section is required")
    seen: set[str] = set()
    for section in selected:
        if section.filing_id != filing.id:
            raise ValueError("sections cannot cross filing identity")
        if section.id in seen:
            raise ValueError("duplicate filing section identity")
        seen.add(section.id)
    return tuple(sorted(selected, key=lambda item: (item.ordinal, item.id)))


def _section_map(
    filing: FilingDocument, sections: Sequence[FilingSection]
) -> dict[str, FilingSection]:
    return {section.id: section for section in _sections_for(filing, sections)}


def _excerpt_for_reference(
    reference: FilingEvidenceReference, section: FilingSection
) -> str:
    """Resolve a reference span and verify its hash against normalized text.

    References produced by this module use absolute section coordinates.  For
    hand-authored fixtures, local normalized-text coordinates are also
    accepted when the absolute interpretation is impossible.  In both cases
    the resulting span is bounded by this exact section and its excerpt hash
    is checked before a claim is constructed.
    """

    if reference.filing_id != section.filing_id or reference.section_id != section.id:
        raise ValueError("evidence reference does not belong to the filing section")

    if (
        section.source_start <= reference.source_start
        and reference.source_end <= section.source_end
    ):
        start = reference.source_start - section.source_start
        end = reference.source_end - section.source_start
    elif reference.source_end <= len(section.normalized_text):
        start = reference.source_start
        end = reference.source_end
    else:
        raise ValueError("evidence span is outside normalized filing section")

    if not 0 <= start < end <= len(section.normalized_text):
        raise ValueError("evidence span is outside normalized section text")
    excerpt = section.normalized_text[start:end]
    if not _hash_matches(reference.excerpt_hash, excerpt):
        raise ValueError("evidence excerpt hash does not match normalized section text")
    return excerpt


def _validate_references(
    filing: FilingDocument,
    sections: Sequence[FilingSection],
    references: Iterable[FilingEvidenceReference],
) -> tuple[FilingEvidenceReference, ...]:
    by_id = _section_map(filing, sections)
    resolved = tuple(references)
    if not resolved:
        raise ValueError("supported claims require at least one evidence reference")
    for reference in resolved:
        section = by_id.get(reference.section_id)
        if section is None:
            raise ValueError("evidence reference points to an unknown filing section")
        _excerpt_for_reference(reference, section)
    return resolved


def _stable_claim_id(
    *,
    ticker: str,
    as_of: date,
    filing_id: str,
    methodology_version: str,
    category: ClaimCategory,
    direction: ClaimDirection,
    statement: str,
    method: ClaimMethod,
    references: Sequence[FilingEvidenceReference],
) -> str:
    payload = {
        "ticker": ticker,
        "as_of": as_of.isoformat(),
        "filing_id": filing_id,
        "methodology_version": methodology_version,
        "category": category.value,
        "direction": direction.value,
        "statement": statement,
        "method": method.value,
        "references": [
            {
                "filing_id": reference.filing_id,
                "section_id": reference.section_id,
                "source_start": reference.source_start,
                "source_end": reference.source_end,
                "excerpt_hash": reference.excerpt_hash,
            }
            for reference in references
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "claim-" + hashlib.sha256(encoded).hexdigest()[:32]


def build_analyst_authored_claim(
    filing: FilingDocument,
    sections: Iterable[FilingSection],
    *,
    as_of: date,
    category: ClaimCategory,
    direction: ClaimDirection,
    statement: str,
    evidence: Iterable[FilingEvidenceReference],
    created_at: datetime,
    methodology_version: str = CLAIMS_ANALYST_VERSION,
) -> QualitativeClaim:
    """Build a supported analyst claim from exact, validated evidence.

    The factory accepts no raw provider payload and performs no text
    interpretation.  A claim cannot be created without a section reference
    whose span and SHA-256 excerpt hash match the persisted normalized text.
    """

    if not filing.is_available_on(as_of):
        raise ValueError("filing is not publicly available at the claim as-of date")
    if not statement.strip():
        raise ValueError("claim statement is required")
    selected = _sections_for(filing, sections)
    references = _validate_references(filing, selected, evidence)
    claim_id = _stable_claim_id(
        ticker=str(filing.ticker),
        as_of=as_of,
        filing_id=filing.id,
        methodology_version=methodology_version,
        category=category,
        direction=direction,
        statement=statement,
        method=ClaimMethod.ANALYST_AUTHORED,
        references=references,
    )
    return QualitativeClaim(
        id=claim_id,
        ticker=filing.ticker,
        as_of=as_of,
        filing_id=filing.id,
        methodology_version=methodology_version,
        category=category,
        direction=direction,
        statement=statement.strip(),
        status=ClaimStatus.SUPPORTED,
        method=ClaimMethod.ANALYST_AUTHORED,
        source_references=references,
        created_at=created_at,
    )


def build_disclosed_risk_claims(
    filing: FilingDocument,
    sections: Iterable[FilingSection],
    *,
    as_of: date,
    patterns: Iterable[DisclosedRiskPattern],
    created_at: datetime,
    methodology_version: str = DISCLOSED_RISK_VERSION,
) -> tuple[QualitativeClaim, ...]:
    """Create one deterministic claim per declared pattern/section match.

    This reports only that the configured text is disclosed in a configured
    section.  It does not infer probability, severity, causality, resolution,
    management intent, or investment impact.
    """

    if not filing.is_available_on(as_of):
        raise ValueError("filing is not publicly available at the claim as-of date")
    selected = _sections_for(filing, sections)
    claims: list[QualitativeClaim] = []
    for pattern in patterns:
        for section in selected:
            if section.kind not in pattern.section_kinds:
                continue
            flags = 0 if pattern.case_sensitive else re.IGNORECASE
            match = re.search(re.escape(pattern.pattern), section.normalized_text, flags)
            if match is None:
                continue
            start = section.source_start + match.start()
            end = section.source_start + match.end()
            excerpt = section.normalized_text[match.start() : match.end()]
            reference = FilingEvidenceReference(
                filing.id, section.id, start, end, normalized_excerpt_hash(excerpt)
            )
            statement = pattern.statement or (
                f"Configured disclosure pattern '{pattern.name}' is present in "
                f"the {section.title} section."
            )
            claim_id = _stable_claim_id(
                ticker=str(filing.ticker),
                as_of=as_of,
                filing_id=filing.id,
                methodology_version=methodology_version,
                category=ClaimCategory.RISK_FACTOR,
                direction=ClaimDirection.NEGATIVE,
                statement=statement,
                method=ClaimMethod.DETERMINISTIC,
                references=(reference,),
            )
            claims.append(
                QualitativeClaim(
                    id=claim_id,
                    ticker=filing.ticker,
                    as_of=as_of,
                    filing_id=filing.id,
                    methodology_version=methodology_version,
                    category=ClaimCategory.RISK_FACTOR,
                    direction=ClaimDirection.NEGATIVE,
                    statement=statement,
                    status=ClaimStatus.SUPPORTED,
                    method=ClaimMethod.DETERMINISTIC,
                    source_references=(reference,),
                    created_at=created_at,
                    metadata={"pattern_name": pattern.name, "section_kind": section.kind.value},
                )
            )
    return tuple(sorted(claims, key=lambda claim: claim.id))


__all__ = [
    "CLAIMS_ANALYST_VERSION",
    "DISCLOSED_RISK_VERSION",
    "DisclosedRiskPattern",
    "build_analyst_authored_claim",
    "build_disclosed_risk_claims",
    "normalized_excerpt_hash",
]
