from datetime import date, datetime, timezone
import hashlib

import pytest

from stocks_investment.domain import (
    ClaimCategory,
    ClaimDirection,
    DataProvenance,
    FilingDocument,
    FilingEvidenceReference,
    FilingForm,
    FilingSection,
    FilingSectionKind,
    Ticker,
)
from stocks_investment.filings.claims import (
    DisclosedRiskPattern,
    build_analyst_authored_claim,
    build_disclosed_risk_claims,
    normalized_excerpt_hash,
)


AS_OF = date(2025, 2, 14)
CREATED = datetime(2025, 2, 15, tzinfo=timezone.utc)


def _filing(identifier: str = "filing-1", available: date = AS_OF) -> FilingDocument:
    available_at = datetime.combine(available, datetime.min.time(), tzinfo=timezone.utc)
    provenance = DataProvenance(
        "sec:archive", "sec-edgar", available_at, available,
        available_at=available_at, filing_date=available, period_end=date(2024, 12, 31),
        raw_identifier=f"{identifier}/annual-report.htm",
    )
    return FilingDocument(
        identifier, Ticker("AAA"), "0000000001", f"0001-25-{identifier[-1]}",
        FilingForm.FORM_10_K, available_at, available_at, date(2024, 12, 31),
        "annual-report.htm", "https://www.sec.gov/Archives/example", "sha256:document",
        available_at, "text/html", 1024, provenance,
    )


def _section(
    filing_id: str = "filing-1",
    identifier: str = "section-risk",
    text: str = "Liquidity risk may adversely affect results.",
    kind: FilingSectionKind = FilingSectionKind.RISK_FACTORS,
    source_start: int = 100,
) -> FilingSection:
    return FilingSection(
        identifier, filing_id, "1A", "Risk Factors", kind, 1, text,
        "sha256:section", source_start, source_start + len(text), "parser_v1",
    )


def _reference(section: FilingSection, excerpt: str, *, local: bool = False) -> FilingEvidenceReference:
    start = section.normalized_text.index(excerpt)
    if not local:
        start += section.source_start
    end = start + len(excerpt)
    return FilingEvidenceReference(section.filing_id, section.id, start, end, normalized_excerpt_hash(excerpt))


def test_analyst_claim_requires_and_preserves_supported_evidence() -> None:
    filing = _filing()
    section = _section()
    claim = build_analyst_authored_claim(
        filing, (section,), as_of=AS_OF, category=ClaimCategory.RISK_FACTOR,
        direction=ClaimDirection.NEGATIVE, statement="Liquidity is disclosed as a risk.",
        evidence=(_reference(section, "Liquidity risk"),), created_at=CREATED,
    )
    assert claim.status.value == "supported"
    assert claim.method.value == "analyst_authored"
    assert claim.source_references[0].section_id == section.id

    with pytest.raises(ValueError, match="require at least one"):
        build_analyst_authored_claim(
            filing, (section,), as_of=AS_OF, category=ClaimCategory.RISK_FACTOR,
            direction=ClaimDirection.NEGATIVE, statement="No evidence.", evidence=(),
            created_at=CREATED,
        )


def test_cross_filing_section_and_altered_hash_are_rejected() -> None:
    filing = _filing()
    other = _section("filing-2", "section-other")
    with pytest.raises(ValueError, match="cross filing"):
        build_analyst_authored_claim(
            filing, (other,), as_of=AS_OF, category=ClaimCategory.RISK_FACTOR,
            direction=ClaimDirection.NEGATIVE, statement="Cross filing.",
            evidence=(_reference(other, "Liquidity risk"),), created_at=CREATED,
        )
    section = _section()
    bad = FilingEvidenceReference(section.filing_id, section.id, 100, 113, "sha256:altered")
    with pytest.raises(ValueError, match="hash"):
        build_analyst_authored_claim(
            filing, (section,), as_of=AS_OF, category=ClaimCategory.RISK_FACTOR,
            direction=ClaimDirection.NEGATIVE, statement="Altered.", evidence=(bad,),
            created_at=CREATED,
        )


def test_claim_ids_are_stable_and_local_spans_are_supported() -> None:
    filing = _filing()
    section = _section()
    kwargs = dict(
        as_of=AS_OF, category=ClaimCategory.RISK_FACTOR, direction=ClaimDirection.NEGATIVE,
        statement="Stable.", created_at=CREATED,
    )
    first = build_analyst_authored_claim(filing, (section,), evidence=(_reference(section, "Liquidity risk", local=True),), **kwargs)
    second = build_analyst_authored_claim(filing, (section,), evidence=(_reference(section, "Liquidity risk", local=True),), **kwargs)
    assert first.id == second.id
    assert first == second


def test_disclosed_risk_claims_are_literal_deterministic_and_evidence_backed() -> None:
    filing = _filing()
    section = _section(text="Liquidity risk may adversely affect results; cyber risk is disclosed.")
    pattern = DisclosedRiskPattern("liquidity", "Liquidity risk")
    claims = build_disclosed_risk_claims(
        filing, (section,), as_of=AS_OF, patterns=(pattern,), created_at=CREATED,
    )
    rerun = build_disclosed_risk_claims(
        filing, (section,), as_of=AS_OF, patterns=(pattern,), created_at=CREATED,
    )
    assert len(claims) == 1
    assert claims == rerun
    assert claims[0].method.value == "deterministic"
    assert claims[0].source_references[0].excerpt_hash == normalized_excerpt_hash("Liquidity risk")


def test_no_claim_without_match_or_with_insufficient_evidence() -> None:
    filing = _filing()
    section = _section(text="The company describes ordinary operations.")
    assert build_disclosed_risk_claims(
        filing, (section,), as_of=AS_OF,
        patterns=(DisclosedRiskPattern("fraud", "fraud"),), created_at=CREATED,
    ) == ()
    with pytest.raises(ValueError, match="outside normalized"):
        build_analyst_authored_claim(
            filing, (section,), as_of=AS_OF, category=ClaimCategory.RISK_FACTOR,
            direction=ClaimDirection.NEGATIVE, statement="Unsupported.",
            evidence=(FilingEvidenceReference(filing.id, section.id, 0, 100, "sha256:x"),),
            created_at=CREATED,
        )


def test_later_filing_does_not_mutate_old_claim_and_future_filing_is_blocked() -> None:
    filing = _filing()
    section = _section()
    old = build_disclosed_risk_claims(
        filing, (section,), as_of=AS_OF,
        patterns=(DisclosedRiskPattern("liquidity", "Liquidity risk"),), created_at=CREATED,
    )[0]
    later = _filing("filing-2", date(2025, 3, 1))
    with pytest.raises(ValueError, match="not publicly available"):
        build_disclosed_risk_claims(
            later, (_section("filing-2", "section-later"),), as_of=AS_OF,
            patterns=(DisclosedRiskPattern("liquidity", "Liquidity risk"),), created_at=CREATED,
        )
    assert old.filing_id == "filing-1"
    assert old.as_of == AS_OF


def test_hash_helper_matches_independent_sha256() -> None:
    excerpt = "Liquidity risk"
    assert normalized_excerpt_hash(excerpt) == "sha256:" + hashlib.sha256(excerpt.encode()).hexdigest()
