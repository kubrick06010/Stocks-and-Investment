from datetime import date, datetime, timezone

from stocks_investment.domain import (
    ResearchResult,
    ResearchRun,
    ResearchRunStatus,
    Ticker,
    WatchCondition,
    WatchlistEntry,
    WatchlistStatus,
)
from stocks_investment.watchlist import evaluate_watchlist


def test_watchlist_emits_only_condition_state_changes() -> None:
    run = ResearchRun(
        "r",
        datetime(2025, 1, 1, tzinfo=timezone.utc),
        date(2025, 1, 1),
        "s",
        "v1",
        "u",
        "u1",
        date(2025, 1, 1),
        {},
        status=ResearchRunStatus.COMPLETED,
    )
    result = ResearchResult("r:A", "r", Ticker("AAA"), run.created_at, 1, 80, "watch")
    entry = WatchlistEntry(
        "w",
        Ticker("AAA"),
        run.created_at,
        "r",
        result.id,
        "quality strong; valuation high",
        WatchlistStatus.ACTIVE,
        target_conditions=(WatchCondition("composite_score", ">=", 80, "w1"),),
    )
    events = evaluate_watchlist(entry, run, result)
    assert len(events) == 1 and events[0].triggered
    assert evaluate_watchlist(entry, run, result, {"composite_score": 80}) == ()
