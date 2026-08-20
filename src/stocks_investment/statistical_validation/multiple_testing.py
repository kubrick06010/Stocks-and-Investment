"""Deterministic multiple-testing corrections for frozen hypothesis results."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Iterable, TypeVar

from stocks_investment.domain.statistical_validation import (
    HypothesisTestResult,
    MultipleTestingMethod,
)


VERSION = "multiple_testing_v1"
T = TypeVar("T")


def adjust_hypotheses(
    results: Iterable[HypothesisTestResult],
    *,
    method: MultipleTestingMethod | None = None,
    alpha: float | None = None,
) -> tuple[HypothesisTestResult, ...]:
    """Adjust one homogeneous hypothesis family.

    The supplied raw p-values are the only statistical inputs.  Results must
    belong to one family and must agree on method and alpha unless those are
    explicitly overridden for the complete family.  A mixed family is
    rejected instead of silently producing a population-dependent correction.
    """

    items = tuple(results)
    if not items:
        return ()

    family_ids = {item.family_id for item in items}
    if len(family_ids) != 1 or not next(iter(family_ids)):
        raise ValueError("multiple-testing correction requires exactly one non-empty family")
    hypothesis_ids = tuple(item.hypothesis_id for item in items)
    if any(not identifier for identifier in hypothesis_ids):
        raise ValueError("hypothesis IDs must not be empty")
    if len(set(hypothesis_ids)) != len(hypothesis_ids):
        raise ValueError("hypothesis IDs must be unique within a family")

    selected_method = method if method is not None else _single_value(
        (item.method for item in items), "method"
    )
    selected_alpha = alpha if alpha is not None else _single_value(
        (item.alpha for item in items), "alpha"
    )
    _validate_method(selected_method)
    _validate_alpha(selected_alpha)

    for item in items:
        _validate_p_value(item.raw_p_value, item.hypothesis_id)
        if method is None and item.method is not selected_method:
            raise ValueError("hypotheses in a family must use one correction method")
        if alpha is None and item.alpha != selected_alpha:
            raise ValueError("hypotheses in a family must use one alpha")

    if selected_method is MultipleTestingMethod.NONE:
        adjusted = {item.hypothesis_id: item.raw_p_value for item in items}
    else:
        ordered = tuple(sorted(items, key=lambda item: (item.raw_p_value, item.hypothesis_id)))
        if selected_method is MultipleTestingMethod.BENJAMINI_HOCHBERG:
            adjusted = _benjamini_hochberg(ordered)
        elif selected_method is MultipleTestingMethod.HOLM_BONFERRONI:
            adjusted = _holm_bonferroni(ordered)
        else:  # pragma: no cover - protected by _validate_method
            raise ValueError(f"unsupported multiple-testing method: {selected_method}")

    output = tuple(
        replace(
            item,
            adjusted_p_value=adjusted[item.hypothesis_id],
            method=selected_method,
            alpha=selected_alpha,
            rejected=adjusted[item.hypothesis_id] <= selected_alpha,
        )
        for item in items
    )
    return tuple(sorted(output, key=lambda item: item.hypothesis_id))


class MultipleTestingAdjusterV1:
    """Small protocol-compatible facade for the V1 correction methodology."""

    version = VERSION

    def adjust(self, results: Iterable[HypothesisTestResult]) -> tuple[HypothesisTestResult, ...]:
        return adjust_hypotheses(results)


def _benjamini_hochberg(
    ordered: tuple[HypothesisTestResult, ...],
) -> dict[str, float]:
    count = len(ordered)
    corrected = [min(1.0, item.raw_p_value * count / rank) for rank, item in enumerate(ordered, 1)]
    for index in range(count - 2, -1, -1):
        corrected[index] = min(corrected[index], corrected[index + 1])
    return {item.hypothesis_id: value for item, value in zip(ordered, corrected)}


def _holm_bonferroni(
    ordered: tuple[HypothesisTestResult, ...],
) -> dict[str, float]:
    count = len(ordered)
    corrected: list[float] = []
    running_max = 0.0
    for index, item in enumerate(ordered):
        running_max = max(running_max, min(1.0, (count - index) * item.raw_p_value))
        corrected.append(running_max)
    return {item.hypothesis_id: value for item, value in zip(ordered, corrected)}


def _single_value(values: Iterable[T], name: str) -> T:
    unique = tuple(dict.fromkeys(values))
    if len(unique) != 1:
        raise ValueError(f"hypotheses in a family must use one {name}")
    return unique[0]


def _validate_method(method: MultipleTestingMethod) -> None:
    if not isinstance(method, MultipleTestingMethod):
        raise ValueError("method must be a MultipleTestingMethod")


def _validate_alpha(alpha: float) -> None:
    if not math.isfinite(alpha) or not 0 < alpha < 1:
        raise ValueError("alpha must be finite and strictly between 0 and 1")


def _validate_p_value(value: float, hypothesis_id: str) -> None:
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"raw p-value for {hypothesis_id!r} must be finite and in 0..1")
