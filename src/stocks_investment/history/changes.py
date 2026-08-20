"""D2 change detection without historical recomputation."""

from __future__ import annotations

from stocks_investment.domain.research import ResearchResult, ResearchRun
from stocks_investment.domain.research_intelligence import (
    ChangeType,
    MaterialityPolicy,
    MaterialityRuleType,
    ResearchChangeEvent,
    SourceReference,
)


def compare_results(
    earlier_run: ResearchRun,
    earlier: ResearchResult,
    later_run: ResearchRun,
    later: ResearchResult,
    policy: MaterialityPolicy,
) -> tuple[ResearchChangeEvent, ...]:
    if (
        earlier.ticker != later.ticker
        or earlier.run_id != earlier_run.id
        or later.run_id != later_run.id
    ):
        raise ValueError("comparison artifacts are not aligned")
    events: list[ResearchChangeEvent] = []
    for rule in policy.rules:
        old, new = _field(earlier, rule.field), _field(later, rule.field)
        if _material(rule.rule_type, rule.threshold, old, new):
            events.append(
                ResearchChangeEvent(
                    earlier.ticker,
                    earlier_run.id,
                    later_run.id,
                    earlier_run.as_of,
                    later_run.as_of,
                    _change_type(rule.field),
                    rule.field,
                    old,
                    new,
                    _magnitude(old, new),
                    f"{policy.version}:{rule.version}",
                    (
                        SourceReference("research_result", earlier.id, rule.field),
                        SourceReference("research_result", later.id, rule.field),
                    ),
                )
            )
    return tuple(events)


def _field(result: ResearchResult, field: str) -> object:
    if field == "rank":
        return result.rank
    if field == "composite_score":
        return result.composite_score
    if field == "classification":
        return result.classification
    for factor in result.factor_scores:
        if factor.factor_name == field:
            return factor.score
    for criterion in result.criteria:
        if criterion.criterion_name == field:
            return criterion.passed
    return None


def _material(kind: MaterialityRuleType, threshold: float | None, old: object, new: object) -> bool:
    if old is None or new is None:
        return old != new
    if kind is MaterialityRuleType.STATUS_TRANSITION:
        return old != new
    if kind is MaterialityRuleType.RANK_MOVEMENT:
        return isinstance(old, int) and isinstance(new, int) and abs(old - new) >= (threshold or 1)
    if not isinstance(old, (int, float)) or not isinstance(new, (int, float)):
        return old != new
    if kind is MaterialityRuleType.RELATIVE:
        return abs(new - old) / abs(old) >= (threshold or 0) if old else True
    return abs(new - old) >= (threshold or 0)


def _magnitude(old: object, new: object) -> float | None:
    return (
        float(new) - float(old)
        if isinstance(old, (int, float)) and isinstance(new, (int, float))
        else None
    )


def _change_type(field: str) -> ChangeType:
    if field == "rank":
        return ChangeType.RANK_CHANGE
    if field == "classification":
        return ChangeType.CLASSIFICATION_CHANGE
    if field in {"composite_score"} or field in {"value", "quality", "growth"}:
        return ChangeType.FACTOR_CHANGE
    return ChangeType.CRITERION_CHANGE
