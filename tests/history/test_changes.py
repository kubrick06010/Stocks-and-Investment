from datetime import date, datetime, timezone

from stocks_investment.domain import (
    MaterialityPolicy,
    MaterialityRule,
    MaterialityRuleType,
    ResearchResult,
    ResearchRun,
    ResearchRunStatus,
    Ticker,
)
from stocks_investment.history import compare_results


def test_change_detector_finds_material_rank_and_status_changes() -> None:
    r0 = ResearchRun(
        "r0",
        datetime(2025, 1, 1, tzinfo=timezone.utc),
        date(2025, 1, 1),
        "s",
        "v1",
        "u",
        "u0",
        date(2025, 1, 1),
        {},
        status=ResearchRunStatus.COMPLETED,
    )
    r1 = ResearchRun(
        "r1",
        datetime(2025, 4, 1, tzinfo=timezone.utc),
        date(2025, 4, 1),
        "s",
        "v1",
        "u",
        "u1",
        date(2025, 4, 1),
        {},
        status=ResearchRunStatus.COMPLETED,
    )
    old, new = (
        ResearchResult("r0:A", "r0", Ticker("AAA"), r0.created_at, 42, 60, "watch"),
        ResearchResult("r1:A", "r1", Ticker("AAA"), r1.created_at, 11, 72, "attractive"),
    )
    policy = MaterialityPolicy(
        "p1",
        (
            MaterialityRule("rank", MaterialityRuleType.RANK_MOVEMENT, 20, "rank_v1"),
            MaterialityRule(
                "classification", MaterialityRuleType.STATUS_TRANSITION, None, "class_v1"
            ),
        ),
    )
    events = compare_results(r0, old, r1, new, policy)
    assert {item.field for item in events} == {"rank", "classification"}
    assert all(item.source_references for item in events)
