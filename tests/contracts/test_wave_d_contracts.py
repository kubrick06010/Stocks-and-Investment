from datetime import date, datetime, timezone

import pytest

from stocks_investment.domain import (
    ChangeType, CohortIdentity, DriverDirection, FactorOutcomeObservation,
    MaterialityPolicy, MaterialityRule, MaterialityRuleType, ResearchChangeEvent,
    ResearchReport, ReportSection, SourceReference, StrategyComparison,
    ThesisClassification, ThesisDriver, ThesisDriverCategory, ThesisSnapshot,
    Ticker, WatchCondition, WatchlistEntry, WatchlistStatus,
)


def ref(entity_id: str = "result-1") -> SourceReference:
    return SourceReference("research_result", entity_id, "composite_score")


def test_thesis_snapshot_requires_immutable_historical_references() -> None:
    driver = ThesisDriver("quality", ThesisDriverCategory.QUALITY, DriverDirection.POSITIVE, .9, "84/100", ref(), "strong")
    snapshot = ThesisSnapshot("thesis-1", Ticker("AAA"), "run-1", "result-1", date(2025, 1, 1),
                              "structured_thesis_v1", ThesisClassification.WATCH, "quality is strong",
                              drivers=(driver,), confidence=.8)
    assert snapshot.research_run_id == "run-1"
    assert snapshot.drivers[0].source_reference == ref()
    with pytest.raises(ValueError):
        ThesisSnapshot("", Ticker("AAA"), "run-1", "result-1", date(2025, 1, 1), "v1", ThesisClassification.WATCH, "")


def test_change_event_and_materiality_policy_are_structured_and_versioned() -> None:
    policy = MaterialityPolicy("materiality_v1", (MaterialityRule("roic", MaterialityRuleType.ABSOLUTE, 3.0, "roic_bps_v1"),))
    event = ResearchChangeEvent(Ticker("AAA"), "run-1", "run-2", date(2025, 1, 1), date(2025, 4, 1),
                                ChangeType.CRITERION_CHANGE, "graham_pe", "fail", "pass", None, "material", (ref(),))
    assert policy.version == "materiality_v1"
    assert event.change_type is ChangeType.CRITERION_CHANGE
    assert event.old_value != event.new_value


def test_strategy_comparison_exposes_fairness_mismatches() -> None:
    comparison = StrategyComparison("graham_v1", "quality_v1", date(2020, 1, 1), date(2025, 1, 1), "sp500",
                                    ("run-1",), top_n_overlap=.4, assumption_mismatches=("different cost model",))
    assert comparison.assumption_mismatches == ("different cost model",)


def test_factor_outcome_keeps_research_date_and_future_horizon_distinct() -> None:
    observation = FactorOutcomeObservation("quality", "quality_v1", "run-1", Ticker("AAA"), date(2025, 1, 1), 84, "12M", .12, .05, .07, "measured", "synthetic", "SYNTH", "USD", "quarterly")
    cohort = CohortIdentity("quality_v1", "sp500", date(2020, 1, 1), date(2025, 1, 1), "12M", "quarterly", "USD", "SPY")
    assert observation.as_of != date(2026, 1, 1)
    assert cohort.outcome_horizon == "12M"


def test_watchlist_preserves_source_reason_and_deterministic_condition() -> None:
    condition = WatchCondition("pe_ttm", "<=", 18, "watch_condition_v1")
    entry = WatchlistEntry("watch-1", Ticker("AAA"), datetime(2025, 1, 1, tzinfo=timezone.utc),
                           "run-1", "result-1", "quality strong, valuation high", WatchlistStatus.ACTIVE,
                           target_conditions=(condition,))
    assert entry.source_result_id == "result-1"
    assert entry.target_conditions[0].threshold == 18


def test_report_sections_keep_source_lineage_and_are_not_format_specific() -> None:
    report = ResearchReport("thesis", date(2025, 1, 1), ("run-1",),
                            (ReportSection("Drivers", "drivers", {"count": 2}, (ref(),)),))
    assert report.sections[0].source_references[0] == ref()
    assert report.sections[0].payload["count"] == 2
