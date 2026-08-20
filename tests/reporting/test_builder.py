from datetime import date, datetime, timezone
import json

from stocks_investment.reporting import (
    build_historical_stock_report,
    build_report,
    render_json,
    render_markdown,
)
from stocks_investment.domain import ReportSection, SourceReference, Ticker
from stocks_investment.domain.research_engine import ResearchOutcome
from stocks_investment.domain.research_intelligence import ThesisClassification, ThesisSnapshot


def test_report_adapters_preserve_sources_without_recomputation() -> None:
    report = build_report(
        "thesis",
        date(2025, 1, 1),
        ("run-1",),
        (
            ReportSection(
                "Thesis", "thesis", {"classification": "watch"}, (SourceReference("result", "r1"),)
            ),
        ),
    )
    assert "run-1" in render_json(report)
    assert "## Thesis" in render_markdown(report)
    assert report.sections[0].source_references[0].entity_id == "r1"


def test_report_structurally_separates_research_from_subsequent_outcome() -> None:
    report = build_report(
        "historical_stock",
        date(2025, 1, 1),
        ("run-t0",),
        (
            ReportSection("RESEARCH AS OF T0", "research", {"classification": "watch", "return": "not_known"}),
            ReportSection("SUBSEQUENT OUTCOME", "outcome", {"forward_return": 5.0}),
        ),
    )
    encoded = render_json(report)
    markdown = render_markdown(report)
    assert '"section_type": "research"' in encoded
    assert '"section_type": "outcome"' in encoded
    assert "## RESEARCH AS OF T0" in markdown
    assert "## SUBSEQUENT OUTCOME" in markdown
    assert report.sections[0].payload["return"] == "not_known"
    decoded = json.loads(encoded)
    assert all(
        section["section_type"] != "research" or "5.0" not in str(section["payload"])
        for section in decoded["sections"]
    )


def test_historical_report_preserves_lineage_and_outcome_boundary() -> None:
    snapshot = ThesisSnapshot(
        "snapshot-t0",
        Ticker("AAA"),
        "run-t0",
        "result-t0",
        date(2024, 3, 31),
        "structured_thesis_v1",
        ThesisClassification.WATCH,
        "quality is strong; valuation needs improvement",
        created_at=datetime(2024, 4, 1, tzinfo=timezone.utc),
    )
    outcome = ResearchOutcome("result-t0", date(2025, 3, 31), "12M", 0.42, 0.10, 0.32)
    report = build_historical_stock_report("AAA", (snapshot,), (), (), (), (outcome,))

    encoded = render_json(report)
    markdown = render_markdown(report)
    research = tuple(section for section in report.sections if section.section_type == "research")
    outcomes = tuple(section for section in report.sections if section.section_type == "outcome")

    assert report.source_run_ids == ("run-t0",)
    assert research and all("forward_return" not in section.payload for section in research)
    assert outcomes[0].payload["outcomes"] == (outcome,)
    assert '"section_type": "outcome"' in encoded
    assert '"entity_type": "research_outcome"' in encoded
    assert markdown.index("## SUBSEQUENT OUTCOME") > markdown.index("## CURRENT RESEARCH STATE")
    assert "Section type: research" in markdown
    assert "Section type: outcome" in markdown


def test_extreme_future_outcome_cannot_enter_historical_sections() -> None:
    snapshot = ThesisSnapshot(
        "snapshot-t0",
        Ticker("AAA"),
        "run-t0",
        "result-t0",
        date(2024, 3, 31),
        "structured_thesis_v1",
        ThesisClassification.WATCH,
        "valuation requires improvement",
    )
    report = build_historical_stock_report(
        "AAA", (snapshot,), (), (), (),
        (ResearchOutcome("result-t0", date(2025, 3, 31), "12M", 5.0, 0.1, 4.9),),
    )
    research_sections = tuple(section for section in report.sections if section.section_type == "research")
    outcome_sections = tuple(section for section in report.sections if section.section_type == "outcome")
    assert all("5.0" not in str(section.payload) for section in research_sections)
    assert "5.0" in str(outcome_sections[0].payload)
