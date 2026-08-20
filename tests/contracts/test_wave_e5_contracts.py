from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from stocks_investment.domain import (
    OutcomeVisibility,
    ReportSection,
    ResearchReport,
    ResearchView,
    ResearchViewKind,
    ResearchViewRequest,
    ResearchViewStatus,
    SourceReference,
)


def test_stock_request_freezes_explicit_outcome_visibility() -> None:
    request = ResearchViewRequest(
        "view-1", ResearchViewKind.STOCK, "interactive_research_v1", "AAA",
        as_of=date(2025, 12, 31), outcome_visibility=OutcomeVisibility.SEPARATE,
    )
    assert request.outcome_visibility is OutcomeVisibility.SEPARATE
    with pytest.raises(FrozenInstanceError):
        request.primary_id = "BBB"  # type: ignore[misc]


def test_strategy_comparison_preserves_both_backtest_identities() -> None:
    request = ResearchViewRequest(
        "compare-1", ResearchViewKind.STRATEGY_COMPARISON,
        "interactive_research_v1", "graham-backtest", "balanced-backtest",
    )
    assert (request.primary_id, request.secondary_id) == (
        "graham-backtest", "balanced-backtest",
    )
    with pytest.raises(ValueError, match="requires two"):
        ResearchViewRequest(
            "bad", ResearchViewKind.STRATEGY_COMPARISON,
            "interactive_research_v1", "graham-backtest",
        )


def test_factor_query_cannot_hide_version_or_horizon_identity() -> None:
    with pytest.raises(ValueError, match="version and horizon"):
        ResearchViewRequest(
            "factor", ResearchViewKind.FACTOR_EFFICACY,
            "interactive_research_v1", "quality",
        )
    request = ResearchViewRequest(
        "factor", ResearchViewKind.FACTOR_EFFICACY,
        "interactive_research_v1", "quality", factor_version="quality_v1",
        horizon="12M",
    )
    assert (request.factor_version, request.horizon) == ("quality_v1", "12M")


def test_query_limits_and_control_character_identifiers_fail_closed() -> None:
    with pytest.raises(ValueError, match="1..500"):
        ResearchViewRequest(
            "view", ResearchViewKind.WATCHLIST, "interactive_research_v1", limit=501
        )
    with pytest.raises(ValueError, match="control"):
        ResearchViewRequest(
            "view", ResearchViewKind.STOCK, "interactive_research_v1", "AAA\x1b[2J"
        )


def test_valid_view_requires_structured_report_and_unique_lineage() -> None:
    reference = SourceReference("research_run", "run-1")
    report = ResearchReport(
        "stock", date(2025, 12, 31), ("run-1",),
        (ReportSection("RESEARCH AS OF", "research", {"ticker": "AAA"}, (reference,)),),
        {"information_boundary": "research_only"},
    )
    view = ResearchView(
        "view", ResearchViewStatus.VALID, report, (), (reference,)
    )
    assert view.report is report
    with pytest.raises(ValueError, match="requires a structured report"):
        ResearchView("bad", ResearchViewStatus.VALID, None, (), ())
    with pytest.raises(ValueError, match="must be unique"):
        ResearchView("bad", ResearchViewStatus.VALID, report, (), (reference, reference))


def test_not_found_view_cannot_smuggle_historical_or_outcome_report() -> None:
    report = ResearchReport("stock", date(2025, 12, 31), (), (), {})
    with pytest.raises(ValueError, match="cannot carry"):
        ResearchView("missing", ResearchViewStatus.NOT_FOUND, report, (), ())
