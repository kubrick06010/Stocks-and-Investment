"""D5 deterministic watch conditions over new ResearchResults."""

from __future__ import annotations

from stocks_investment.domain.research import ResearchResult, ResearchRun
from stocks_investment.domain.research_intelligence import (
    MonitoringEvent,
    WatchCondition,
    WatchlistEntry,
)


def evaluate_watchlist(
    entry: WatchlistEntry,
    run: ResearchRun,
    result: ResearchResult,
    previous_states: dict[str, object] | None = None,
) -> tuple[MonitoringEvent, ...]:
    if entry.ticker != result.ticker or result.run_id != run.id:
        raise ValueError("watchlist and research artifacts are not aligned")
    previous_states = previous_states or {}
    events: list[MonitoringEvent] = []
    for condition in entry.target_conditions:
        current = _value(result, condition.subject)
        previous = previous_states.get(condition.subject)
        triggered = _matches(condition, current)
        if previous is not None and _matches(condition, previous) == triggered:
            continue
        events.append(
            MonitoringEvent(
                entry.id,
                run.id,
                run.as_of,
                condition,
                previous,
                current,
                triggered,
                f"{condition.subject} {condition.operator} {condition.threshold!r}",
            )
        )
    return tuple(events)


def _value(result: ResearchResult, subject: str) -> object:
    if subject == "rank":
        return result.rank
    if subject == "composite_score":
        return result.composite_score
    if subject == "classification":
        return result.classification
    for factor in result.factor_scores:
        if factor.factor_name == subject:
            return factor.score
    for criterion in result.criteria:
        if criterion.criterion_name == subject:
            # Numeric conditions inspect the observed value; status conditions
            # can still use the explicit pass/fail state.
            return criterion.observed if criterion.observed is not None else criterion.passed
    return None


def _matches(condition: WatchCondition, current: object) -> bool:
    if condition.operator in {"status_transition", "PASS→FAIL", "FAIL→PASS"}:
        return current == condition.threshold
    if current is None:
        return False
    if condition.operator == "==":
        return current == condition.threshold
    if not isinstance(current, (int, float)) or not isinstance(condition.threshold, (int, float)):
        raise ValueError("numeric watch operators require numeric values")
    try:
        return {
            "<": current < condition.threshold,
            "<=": current <= condition.threshold,
            ">": current > condition.threshold,
            ">=": current >= condition.threshold,
        }[condition.operator]
    except (KeyError, TypeError):
        raise ValueError(f"unsupported watch condition: {condition.operator}") from None
