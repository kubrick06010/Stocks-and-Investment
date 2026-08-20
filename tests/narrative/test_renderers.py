from datetime import date

from stocks_investment.domain import (
    NarrativePolicy,
    NarrativeRequest,
    NarrativeStatus,
    ReportSection,
    ResearchReport,
    SourceReference,
)
from stocks_investment.narrative import DisabledNarrativeRenderer, StructuredNarrativeRenderer


def _report() -> ResearchReport:
    return ResearchReport(
        "historical_stock", date(2025, 12, 31), ("run-t0",),
        (
            ReportSection("Research", "research", {"classification": "watch"}, (SourceReference("thesis", "t0"),)),
            ReportSection("Outcome", "outcome", {"return": 500.0}, (SourceReference("outcome", "o1"),)),
        ),
    )


def test_structured_renderer_is_deterministic_and_excludes_outcomes_by_default() -> None:
    request = NarrativeRequest(_report(), NarrativePolicy("structured", "policy_v1"))
    renderer = StructuredNarrativeRenderer()
    first = renderer.render(request)
    second = renderer.render(request)
    assert first == second
    assert first.status is NarrativeStatus.GENERATED
    assert "500.0" not in first.text
    assert "SUBSEQUENT OUTCOME" not in first.text
    assert first.source_references == (SourceReference("thesis", "t0"),)


def test_structured_renderer_keeps_future_outcomes_in_explicit_boundary() -> None:
    request = NarrativeRequest(_report(), NarrativePolicy("structured", "policy_v1", True))
    result = StructuredNarrativeRenderer().render(request)
    assert "RESEARCH AS OF" in result.text
    assert "SUBSEQUENT OUTCOME" in result.text
    assert "500.0" in result.text
    assert result.information_boundary == "research_then_outcome"


def test_disabled_llm_renderer_is_explicit_and_provider_free() -> None:
    result = DisabledNarrativeRenderer().render(
        NarrativeRequest(_report(), NarrativePolicy("optional_llm", "disabled_v1"))
    )
    assert result.status is NarrativeStatus.DISABLED
    assert result.text == ""
    assert result.source_references == (SourceReference("thesis", "t0"),)
