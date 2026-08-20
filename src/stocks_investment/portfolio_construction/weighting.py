"""Pure base weighting from frozen :class:`ResearchResult` records.

This module deliberately stops at mechanical, security-keyed target weights. It
does not fetch data, select a strategy, apply constraints, or mutate a ledger.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Iterable

from stocks_investment.domain.portfolio_construction import WeightingMethod
from stocks_investment.domain.research import ResearchResult


class EligibilityMode(StrEnum):
    """The persisted selection state accepted by the weighting step."""

    SELECTED = "selected"
    RANKED = "ranked"


class WeightingStatus(StrEnum):
    """Outcome of the pure weighting calculation."""

    VALID = "valid"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True, slots=True)
class WeightedTarget:
    """One deterministic target weight and its persisted research source."""

    ticker: str
    result_id: str
    weight: float
    score: float | None


@dataclass(frozen=True, slots=True)
class WeightingIssue:
    """An input that prevented a score-proportional allocation."""

    ticker: str
    result_id: str
    reason: str
    score: float | None


@dataclass(frozen=True, slots=True)
class BaseWeightingResult:
    """Small lead-integration result; no persistence or portfolio side effects."""

    run_id: str
    method: WeightingMethod
    eligibility: EligibilityMode
    status: WeightingStatus
    targets: tuple[WeightedTarget, ...]
    issues: tuple[WeightingIssue, ...] = ()


def build_base_weights(
    results: Iterable[ResearchResult],
    *,
    run_id: str,
    method: WeightingMethod | str,
    eligibility: EligibilityMode | str,
) -> BaseWeightingResult:
    """Build deterministic base weights from results belonging to ``run_id``.

    ``selected`` means a result has ``classification == "selected"`` and a
    positive persisted rank. ``ranked`` means any result with a positive rank;
    this is useful when a caller intentionally wants to weight a frozen ranking
    without requiring the screening label. The choice is never inferred.

    Equal weighting does not need a score. Score-proportional weighting requires
    every eligible score to be finite and strictly positive. If one is missing,
    zero, negative, or non-finite, the result is explicitly
    ``INSUFFICIENT_DATA`` and contains no partial allocation.
    """

    if not run_id.strip():
        raise ValueError("run_id is required")
    normalized_method = _method(method)
    normalized_eligibility = _eligibility(eligibility)
    rows = tuple(results)
    for result in rows:
        if result.run_id != run_id:
            raise ValueError(
                f"ResearchResult {result.id} belongs to run {result.run_id!r}, "
                f"not requested run {run_id!r}"
            )

    eligible = tuple(result for result in rows if _is_eligible(result, normalized_eligibility))
    symbols = tuple(result.ticker.symbol for result in eligible)
    if len(symbols) != len(set(symbols)):
        raise ValueError("eligible ResearchResults must contain unique ticker identities")
    ordered = tuple(sorted(eligible, key=lambda result: result.ticker.symbol))

    if not ordered:
        return BaseWeightingResult(
            run_id, normalized_method, normalized_eligibility,
            WeightingStatus.INSUFFICIENT_DATA, (),
            (WeightingIssue("", "", "no eligible ranked results", None),),
        )

    issue_list: list[WeightingIssue] = []
    for result in ordered:
        issue = _score_issue(result)
        if issue is not None:
            issue_list.append(issue)
    issues = tuple(issue_list)
    if normalized_method is WeightingMethod.SCORE_PROPORTIONAL and issues:
        return BaseWeightingResult(
            run_id, normalized_method, normalized_eligibility,
            WeightingStatus.INSUFFICIENT_DATA, (),
            tuple(issue for issue in issues if issue is not None),
        )

    if normalized_method is WeightingMethod.EQUAL_WEIGHT:
        weight = 1.0 / len(ordered)
        targets = tuple(
            WeightedTarget(result.ticker.symbol, result.id, weight, result.composite_score)
            for result in ordered
        )
    else:
        scores = tuple(result.composite_score for result in ordered)
        if any(score is None for score in scores):
            raise AssertionError("score-proportional validation failed to reject a missing score")
        numeric_scores = tuple(score for score in scores if score is not None)
        total = sum(numeric_scores)
        targets = tuple(
            WeightedTarget(
                result.ticker.symbol,
                result.id,
                result.composite_score / total if result.composite_score is not None else 0.0,
                result.composite_score,
            )
            for result in ordered
        )
    return BaseWeightingResult(
        run_id, normalized_method, normalized_eligibility, WeightingStatus.VALID, targets
    )


def _is_eligible(result: ResearchResult, eligibility: EligibilityMode) -> bool:
    if result.rank is None or result.rank <= 0:
        return False
    return eligibility is EligibilityMode.RANKED or result.classification == "selected"


def _score_issue(result: ResearchResult) -> WeightingIssue | None:
    score = result.composite_score
    if score is None:
        reason = "missing composite score"
    elif not isfinite(score):
        reason = "non-finite composite score"
    elif score <= 0:
        reason = "composite score must be positive"
    else:
        return None
    return WeightingIssue(result.ticker.symbol, result.id, reason, score)


def _method(method: WeightingMethod | str) -> WeightingMethod:
    try:
        return method if isinstance(method, WeightingMethod) else WeightingMethod(method)
    except ValueError as exc:
        raise ValueError(f"unsupported weighting method: {method!r}") from exc


def _eligibility(eligibility: EligibilityMode | str) -> EligibilityMode:
    try:
        return eligibility if isinstance(eligibility, EligibilityMode) else EligibilityMode(eligibility)
    except ValueError as exc:
        raise ValueError(f"unsupported eligibility mode: {eligibility!r}") from exc
