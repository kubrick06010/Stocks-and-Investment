from datetime import date

import pytest

from stocks_investment.domain import (
    NarrativePolicy,
    NarrativeRequest,
    NarrativeStatus,
    ReportSection,
    ResearchReport,
    SourceReference,
)


def _report() -> ResearchReport:
    return ResearchReport(
        "historical_stock", date(2025, 12, 31), ("run-t0",),
        (
            ReportSection("Research", "research", {"classification": "watch"}, (SourceReference("thesis", "t0"),)),
            ReportSection("Outcome", "outcome", {"return": 5.0}, (SourceReference("outcome", "o1"),)),
        ),
    )


def test_narrative_policy_is_explicit_and_bounded() -> None:
    policy = NarrativePolicy("structured", "structured_narrative_v1")
    assert not policy.include_outcomes
    with pytest.raises(ValueError, match="max_characters"):
        NarrativePolicy("structured", "v1", max_characters=0)


def test_narrative_request_consumes_report_not_raw_provider_payload() -> None:
    request = NarrativeRequest(_report(), NarrativePolicy("structured", "v1"))
    assert request.report.report_type == "historical_stock"


def test_narrative_result_boundary_and_status_are_structured() -> None:
    from stocks_investment.domain import NarrativeResult

    result = NarrativeResult("optional_llm", "disabled_v1", "policy_v1", NarrativeStatus.DISABLED, "", (), "research_only")
    assert result.status is NarrativeStatus.DISABLED
    with pytest.raises(ValueError, match="requires text"):
        NarrativeResult("structured", "v1", "policy_v1", NarrativeStatus.GENERATED, "", (), "research_only")
