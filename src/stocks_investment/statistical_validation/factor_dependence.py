"""Identity-safe factor dependence and interaction diagnostics.

The functions in this module are descriptive diagnostics over frozen,
persisted-style observations.  They align by ``(ticker, as_of)`` and never
use positional lists.  No weights are fitted and no investment conclusion is
implied by a correlation or interaction value.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite
from statistics import mean
from typing import Iterable

from stocks_investment.domain.models import Ticker
from stocks_investment.domain.statistical_validation import StatisticalStatus


@dataclass(frozen=True, slots=True)
class FactorDependenceObservation:
    """A factor value with the identity needed for pairwise diagnostics."""

    ticker: Ticker
    as_of: date
    factor_name: str
    factor_version: str
    value: float | None
    universe: str
    status: StatisticalStatus = StatisticalStatus.VALID

    def __post_init__(self) -> None:
        if not self.factor_name.strip() or not self.factor_version.strip() or not self.universe.strip():
            raise ValueError("factor identity and universe are required")
        if self.status is StatisticalStatus.VALID and self.value is None:
            raise ValueError("valid factor observations require a value")
        if self.value is not None and not isfinite(self.value):
            raise ValueError("factor values must be finite")


@dataclass(frozen=True, slots=True)
class FactorDependenceResult:
    """Descriptive dependence for two factors within one frozen cohort."""

    factor_a: str
    factor_a_version: str
    factor_b: str
    factor_b_version: str
    universe: str
    date_start: date
    date_end: date
    eligible_keys: int
    shared_sample_size: int
    coverage: float
    spearman_correlation: float | None
    status: StatisticalStatus

    def __post_init__(self) -> None:
        if self.date_end < self.date_start:
            raise ValueError("date range is invalid")
        if self.eligible_keys < 0 or not 0 <= self.shared_sample_size <= self.eligible_keys:
            raise ValueError("invalid dependence sample counts")
        if not 0 <= self.coverage <= 1:
            raise ValueError("coverage must be in 0..1")
        if self.spearman_correlation is not None and not -1 <= self.spearman_correlation <= 1:
            raise ValueError("correlation must be in -1..1")


@dataclass(frozen=True, slots=True)
class FactorInteractionResult:
    """A predeclared, equal-scale interaction diagnostic."""

    factor_a: str
    factor_b: str
    universe: str
    date_start: date
    date_end: date
    eligible_keys: int
    shared_sample_size: int
    coverage: float
    mean_interaction_score: float | None
    status: StatisticalStatus
    methodology_version: str


def calculate_factor_dependence(
    factor_a: Iterable[FactorDependenceObservation],
    factor_b: Iterable[FactorDependenceObservation],
    *,
    universe: str,
    date_start: date,
    date_end: date,
    minimum_observations: int = 2,
) -> FactorDependenceResult:
    """Calculate tied-rank Spearman correlation after identity-safe joining."""

    if not universe.strip() or date_end < date_start:
        raise ValueError("valid universe and date range are required")
    if minimum_observations < 2:
        raise ValueError("minimum_observations must be at least 2")
    left = _validated_index(tuple(factor_a), universe, date_start, date_end)
    right = _validated_index(tuple(factor_b), universe, date_start, date_end)
    if not left or not right:
        raise ValueError("both factors require observations")
    left_factor = _identity(left)
    right_factor = _identity(right)
    if left_factor == right_factor:
        raise ValueError("factor pair must contain two distinct factor identities")
    keys = tuple(sorted(set(left) | set(right)))
    shared_keys = tuple(sorted(set(left) & set(right)))
    paired = tuple(
        (left[key], right[key])
        for key in shared_keys
        if left[key].status is StatisticalStatus.VALID
        and right[key].status is StatisticalStatus.VALID
        and left[key].value is not None
        and right[key].value is not None
    )
    usable = len(paired)
    status = StatisticalStatus.VALID if usable >= minimum_observations else (
        StatisticalStatus.INSUFFICIENT_COVERAGE if usable < len(keys) else StatisticalStatus.INSUFFICIENT_SAMPLE
    )
    correlation = _spearman(
        tuple(row[0].value for row in paired if row[0].value is not None),
        tuple(row[1].value for row in paired if row[1].value is not None),
    ) if status is StatisticalStatus.VALID else None
    return FactorDependenceResult(
        left_factor[0], left_factor[1], right_factor[0], right_factor[1], universe,
        date_start, date_end, len(keys), usable, usable / len(keys), correlation, status,
    )


def calculate_value_quality_interaction(
    value: Iterable[FactorDependenceObservation],
    quality: Iterable[FactorDependenceObservation],
    *,
    universe: str,
    date_start: date,
    date_end: date,
    minimum_observations: int = 2,
    methodology_version: str = "value_quality_interaction_v1",
) -> FactorInteractionResult:
    """Calculate the predeclared interaction ``Value × Quality / 100``.

    Inputs are expected to be normalized 0..100 factor scores.  This is a
    descriptive interaction diagnostic with fixed equal scaling; it does not
    optimize weights or select securities.
    """

    left = tuple(value)
    right = tuple(quality)
    _require_factor_name(left, "Value")
    _require_factor_name(right, "Quality")
    _validate_scale(left + right)
    dependence = calculate_factor_dependence(
        left, right, universe=universe, date_start=date_start, date_end=date_end,
        minimum_observations=minimum_observations,
    )
    left_index = _validated_index(left, universe, date_start, date_end)
    right_index = _validated_index(right, universe, date_start, date_end)
    keys = tuple(sorted(set(left_index) | set(right_index)))
    scores_list: list[float] = []
    for key in keys:
        left_row, right_row = left_index.get(key), right_index.get(key)
        if left_row is None or right_row is None:
            continue
        if left_row.status is not StatisticalStatus.VALID or right_row.status is not StatisticalStatus.VALID:
            continue
        if left_row.value is None or right_row.value is None:
            continue
        scores_list.append((left_row.value * right_row.value) / 100.0)
    scores = tuple(scores_list)
    return FactorInteractionResult(
        "Value", "Quality", universe, date_start, date_end, len(keys), len(scores),
        len(scores) / len(keys), mean(scores) if dependence.status is StatisticalStatus.VALID else None,
        dependence.status, methodology_version,
    )


def _validated_index(
    rows: tuple[FactorDependenceObservation, ...], universe: str, start: date, end: date
) -> dict[tuple[str, date], FactorDependenceObservation]:
    result: dict[tuple[str, date], FactorDependenceObservation] = {}
    for row in rows:
        if row.universe != universe or not start <= row.as_of <= end:
            raise ValueError("factor observations have incompatible universe or date range")
        key = (row.ticker.symbol, row.as_of)
        if key in result:
            raise ValueError(f"duplicate factor observation for {key[0]} on {key[1]}")
        result[key] = row
    return result


def _identity(index: dict[tuple[str, date], FactorDependenceObservation]) -> tuple[str, str]:
    identities = {(row.factor_name, row.factor_version) for row in index.values()}
    if len(identities) != 1:
        raise ValueError("factor observations mix factor identities")
    return next(iter(identities))


def _require_factor_name(rows: tuple[FactorDependenceObservation, ...], expected: str) -> None:
    if not rows or any(row.factor_name.casefold() != expected.casefold() for row in rows):
        raise ValueError(f"interaction requires {expected} observations")


def _validate_scale(rows: tuple[FactorDependenceObservation, ...]) -> None:
    for row in rows:
        if row.value is not None and not 0 <= row.value <= 100:
            raise ValueError("Value and Quality interaction requires scores in 0..100")


def _spearman(left: tuple[float, ...], right: tuple[float, ...]) -> float | None:
    if len(left) < 2 or len(left) != len(right):
        return None
    return _pearson(_average_ranks(left), _average_ranks(right))


def _average_ranks(values: tuple[float, ...]) -> tuple[float, ...]:
    ranked = sorted(enumerate(values), key=lambda item: (item[1], item[0]))
    ranks = [0.0] * len(values)
    start = 0
    while start < len(ranked):
        end = start + 1
        while end < len(ranked) and ranked[end][1] == ranked[start][1]:
            end += 1
        rank = (start + 1 + end) / 2.0
        for index in range(start, end):
            ranks[ranked[index][0]] = rank
        start = end
    return tuple(ranks)


def _pearson(left: tuple[float, ...], right: tuple[float, ...]) -> float | None:
    left_mean, right_mean = mean(left), mean(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    left_scale = sum((a - left_mean) ** 2 for a in left)
    right_scale = sum((b - right_mean) ** 2 for b in right)
    if left_scale == 0 or right_scale == 0:
        return None
    return float(numerator / (left_scale * right_scale) ** 0.5)
