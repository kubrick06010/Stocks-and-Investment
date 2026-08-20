from datetime import date, datetime, timezone

import pytest

from stocks_investment.domain.filings import FilingDocument, FilingSection, FilingSectionKind
from stocks_investment.domain.models import DataProvenance, Ticker
from stocks_investment.filings.history import FilingHistoryComparator, SectionDiffPolicy


UTC = timezone.utc


def _filing(identifier: str, day: int, *, ticker: str = "AAA", form: str = "10-K") -> FilingDocument:
    from stocks_investment.domain.filings import FilingForm

    available = datetime(2024, 1, day, tzinfo=UTC)
    return FilingDocument(
        id=identifier,
        ticker=Ticker(ticker),
        cik="0000000001",
        accession_number=f"0000000001-24-00000{day}",
        form=FilingForm(form),
        filed_at=available,
        available_at=available,
        period_end=date(2023, 12, 31),
        primary_document=f"{identifier}.htm",
        source_url=f"https://example.test/{identifier}",
        content_hash=f"document-{identifier}",
        retrieved_at=available,
        mime_type="text/html",
        size_bytes=100,
        provenance=DataProvenance(
            source="fixture",
            provider="offline",
            retrieved_at=available,
            effective_date=available.date(),
            available_at=available,
            filing_date=available.date(),
        ),
    )


def _section(
    filing_id: str,
    section_id: str,
    item: str,
    kind: FilingSectionKind,
    text: str,
    ordinal: int,
    *,
    parser_version: str = "parser_v1",
) -> FilingSection:
    return FilingSection(
        id=section_id,
        filing_id=filing_id,
        item=item,
        title=item,
        kind=kind,
        ordinal=ordinal,
        normalized_text=text,
        content_hash=f"hash-{section_id}",
        source_start=ordinal * 100 + 1,
        source_end=ordinal * 100 + 90,
        parser_version=parser_version,
    )


def test_reorders_by_identity_and_marks_tiny_noise_unchanged() -> None:
    before = _filing("f0", 1)
    after = _filing("f1", 2)
    old = [
        _section("f0", "risk0", "Item 1A", FilingSectionKind.RISK_FACTORS, "Risk operations stable.", 0),
        _section("f0", "business0", "Item 1", FilingSectionKind.BUSINESS, "We sell products.", 1),
    ]
    new = [
        _section("f1", "business1", " item   1 ", FilingSectionKind.BUSINESS, "We sell products!", 0),
        _section("f1", "risk1", "ITEM 1A", FilingSectionKind.RISK_FACTORS, "Risk operations stable.", 1),
    ]
    changes = FilingHistoryComparator().compare(before, old, after, new)
    assert [change.change_type.value for change in changes] == ["section_unchanged", "section_unchanged"]
    assert changes[0].from_section_id == "business0"
    assert changes[0].to_section_id == "business1"
    assert changes[0].source_references


def test_added_removed_and_material_modification() -> None:
    before = _filing("f0", 1)
    after = _filing("f1", 2)
    old = [_section("f0", "risk0", "Item 1A", FilingSectionKind.RISK_FACTORS, "Stable operations and demand.", 0)]
    new = [
        _section("f1", "business1", "Item 1", FilingSectionKind.BUSINESS, "A new business section.", 0),
        _section("f1", "risk1", "Item 1A", FilingSectionKind.RISK_FACTORS, "A materially different disclosure about liquidity and litigation.", 1),
    ]
    changes = FilingHistoryComparator().compare(before, old, after, new)
    assert {change.change_type.value for change in changes} == {"section_added", "section_modified"}
    modified = next(change for change in changes if change.change_type.value == "section_modified")
    assert modified.material is True
    assert modified.similarity is not None

    removed = FilingHistoryComparator().compare(
        before,
        old + [_section("f0", "controls0", "Item 4", FilingSectionKind.CONTROLS, "Controls existed.", 1)],
        after,
        new,
    )
    removed_change = next(change for change in removed if change.change_type.value == "section_removed")
    assert removed_change.from_section_id == "controls0"
    assert removed_change.to_section_id is None


def test_rejects_identity_time_parser_and_duplicates() -> None:
    comparator = FilingHistoryComparator()
    section = _section("f0", "s", "Item 1", FilingSectionKind.BUSINESS, "text", 0)
    with pytest.raises(ValueError, match="matching tickers"):
        comparator.compare(_filing("f0", 1), [section], _filing("f1", 2, ticker="BBB"), [])
    with pytest.raises(ValueError, match="future to past"):
        comparator.compare(_filing("f0", 2), [section], _filing("f1", 1), [])
    duplicate = _section("f0", "s2", "ITEM 1", FilingSectionKind.BUSINESS, "text", 1)
    with pytest.raises(ValueError, match="duplicate"):
        comparator.compare(_filing("f0", 1), [section, duplicate], _filing("f1", 2), [])
    mismatch = _section("f1", "s2", "Item 1", FilingSectionKind.BUSINESS, "text", 0, parser_version="parser_v2")
    with pytest.raises(ValueError, match="parser-version"):
        comparator.compare(_filing("f0", 1), [section], _filing("f1", 2), [mismatch])


def test_amendment_is_distinct_and_rerun_is_deterministic() -> None:
    before = _filing("original", 1, form="10-K")
    amendment = _filing("amendment", 2, form="10-K/A")
    old = [_section("original", "risk0", "Item 1A", FilingSectionKind.RISK_FACTORS, "Risk stable.", 0)]
    new = [_section("amendment", "risk1", "Item 1A", FilingSectionKind.RISK_FACTORS, "Risk changed materially.", 0)]
    first = FilingHistoryComparator().compare(before, old, amendment, new)
    second = FilingHistoryComparator().compare(before, old, amendment, new)
    assert first == second
    assert first[0].from_filing_id == "original"
    assert first[0].to_filing_id == "amendment"


def test_thresholds_are_versioned_and_parser_opt_in_is_explicit() -> None:
    policy = SectionDiffPolicy(
        methodology_version="filing_section_diff_v2",
        unchanged_similarity_threshold=1.0,
        material_similarity_threshold=0.5,
    )
    before = _filing("f0", 1)
    after = _filing("f1", 2)
    old = [_section("f0", "s0", "Item 1", FilingSectionKind.BUSINESS, "same", 0)]
    new = [_section("f1", "s1", "Item 1", FilingSectionKind.BUSINESS, "same", 0, parser_version="parser_v2")]
    changes = FilingHistoryComparator(policy, allow_parser_mismatch=True).compare(before, old, after, new)
    assert changes[0].methodology_version == "filing_section_diff_v2"
