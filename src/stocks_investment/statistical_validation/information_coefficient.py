"""Cross-sectional information-coefficient calculations.

This module is deliberately pure.  It consumes frozen outcome observations and
cohort identities; it never fetches data or fills missing outcomes.  Dates and
tickers remain explicit throughout the calculation so that a cross-section is
not accidentally turned into a pooled, positionally aligned correlation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import mean, median, pstdev
from typing import Iterable, Mapping

from stocks_investment.domain.research_intelligence import (
    CohortIdentity,
    FactorOutcomeObservation,
)
from stocks_investment.domain.statistical_validation import (
    CrossSectionalICObservation,
    StatisticalStatus,
    ValidationCohort,
)


@dataclass(frozen=True, slots=True)
class ICStabilitySummary:
    """Equal-date summary of cross-sectional IC observations."""

    factor_name: str
    factor_version: str
    cohort_id: str
    observations: tuple[CrossSectionalICObservation, ...]
    total_dates: int
    usable_dates: int
    eligible_observations: int
    usable_observations: int
    mean_ic: float | None
    median_ic: float | None
    ic_volatility: float | None
    positive_ic_date_hit_rate: float | None
    status: StatisticalStatus


@dataclass(frozen=True, slots=True)
class ICDecayPoint:
    """Stability statistics for one separately supplied outcome horizon."""

    horizon: str
    summary: ICStabilitySummary


@dataclass(frozen=True, slots=True)
class ICDecaySummary:
    """Descriptive IC decay across compatible, separately supplied horizons."""

    factor_name: str
    factor_version: str
    points: tuple[ICDecayPoint, ...]
    status: StatisticalStatus


def calculate_cross_sectional_ic(
    observations: Iterable[FactorOutcomeObservation],
    cohort: ValidationCohort,
    *,
    minimum_observations: int = 10,
) -> tuple[CrossSectionalICObservation, ...]:
    """Calculate one Spearman IC observation per research date.

    The rank correlation is computed only among rows with both a factor score
    and an excess return.  Missing rows are retained in the date-level sample
    accounting, never interpreted as zero.  Tied values receive average ranks.
    """

    if minimum_observations < 2:
        raise ValueError("minimum_observations must be at least 2")
    rows = tuple(observations)
    _validate_cohort(rows, cohort.identity)
    by_date: dict[date, list[FactorOutcomeObservation]] = {}
    for row in rows:
        by_date.setdefault(row.as_of, []).append(row)

    result: list[CrossSectionalICObservation] = []
    for as_of in sorted(by_date):
        date_rows = by_date[as_of]
        symbols = [row.ticker.symbol for row in date_rows]
        if len(symbols) != len(set(symbols)):
            raise ValueError(f"duplicate ticker in cross-section at {as_of}")
        usable = tuple(
            row
            for row in date_rows
            if row.factor_score is not None and row.excess_return is not None
        )
        sample_size = len(usable)
        missing = len(date_rows) - sample_size
        if sample_size < minimum_observations:
            status = (
                StatisticalStatus.INSUFFICIENT_COVERAGE
                if missing
                else StatisticalStatus.INSUFFICIENT_SAMPLE
            )
            rank_ic = None
        else:
            rank_ic = _spearman(
                tuple(row.factor_score for row in usable if row.factor_score is not None),
                tuple(row.excess_return for row in usable if row.excess_return is not None),
            )
            status = StatisticalStatus.VALID if rank_ic is not None else StatisticalStatus.NOT_APPLICABLE
        result.append(
            CrossSectionalICObservation(
                as_of,
                date_rows[0].factor_name,
                cohort.identity.factor_version,
                cohort.identity.outcome_horizon,
                cohort.identity.universe,
                cohort.identity.benchmark,
                sample_size,
                rank_ic,
                status,
            )
        )
    return tuple(result)


def summarize_ic_stability(
    observations: Iterable[CrossSectionalICObservation],
    cohort: ValidationCohort,
) -> ICStabilitySummary:
    """Aggregate date-level IC equally by research date."""

    date_observations = tuple(observations)
    _validate_ic_observations(date_observations, cohort.identity)
    valid = tuple(item for item in date_observations if item.rank_ic is not None)
    values = tuple(item.rank_ic for item in valid if item.rank_ic is not None)
    usable_observations = sum(item.sample_size for item in valid)
    if not values:
        status = StatisticalStatus.INSUFFICIENT_SAMPLE
        summary_values: tuple[float | None, ...] = (None, None, None, None)
    else:
        status = StatisticalStatus.VALID
        summary_values = (
            mean(values),
            median(values),
            pstdev(values) if len(values) > 1 else 0.0,
            sum(value > 0 for value in values) / len(values),
        )
    return ICStabilitySummary(
        date_observations[0].factor_name if date_observations else cohort.identity.factor_version,
        cohort.identity.factor_version,
        cohort.id,
        date_observations,
        len(date_observations),
        len(valid),
        sum(item.sample_size for item in date_observations),
        usable_observations,
        summary_values[0],
        summary_values[1],
        summary_values[2],
        summary_values[3],
        status,
    )


def calculate_ic_decay(
    observations_by_horizon: Mapping[str, Iterable[FactorOutcomeObservation]],
    cohorts_by_horizon: Mapping[str, ValidationCohort],
    *,
    minimum_observations: int = 10,
) -> ICDecaySummary:
    """Calculate stability separately for each supplied horizon.

    Horizons are never pooled.  Each mapping entry must have a matching
    cohort, and all non-horizon cohort identity fields must agree.
    """

    if not observations_by_horizon:
        raise ValueError("at least one horizon is required")
    points: list[ICDecayPoint] = []
    factor_name: str | None = None
    factor_version: str | None = None
    base_identity: CohortIdentity | None = None
    for horizon in sorted(observations_by_horizon):
        if horizon not in cohorts_by_horizon:
            raise ValueError(f"missing cohort for horizon {horizon}")
        cohort = cohorts_by_horizon[horizon]
        identity = cohort.identity
        if identity.outcome_horizon != horizon:
            raise ValueError(f"horizon key {horizon} does not match cohort identity")
        if base_identity is None:
            base_identity = identity
        elif _identity_without_horizon(identity) != _identity_without_horizon(base_identity):
            raise ValueError("IC decay horizons do not share cohort identity")
        date_ic = calculate_cross_sectional_ic(
            observations_by_horizon[horizon], cohort, minimum_observations=minimum_observations
        )
        summary = summarize_ic_stability(date_ic, cohort)
        factor_name = factor_name or summary.factor_name
        factor_version = factor_version or summary.factor_version
        points.append(ICDecayPoint(horizon, summary))
    return ICDecaySummary(
        factor_name or "",
        factor_version or "",
        tuple(points),
        StatisticalStatus.VALID if any(point.summary.status is StatisticalStatus.VALID for point in points) else StatisticalStatus.INSUFFICIENT_SAMPLE,
    )


def _validate_cohort(rows: tuple[FactorOutcomeObservation, ...], identity: CohortIdentity) -> None:
    for row in rows:
        if (
            row.factor_version != identity.factor_version
            or row.universe != identity.universe
            or row.horizon != identity.outcome_horizon
            or row.rebalance_cadence != identity.rebalance_cadence
            or row.base_currency != identity.base_currency
            or row.benchmark != identity.benchmark
            or not identity.date_start <= row.as_of <= identity.date_end
        ):
            raise ValueError(
                f"observation {row.research_run_id} does not belong to cohort identity"
            )


def _validate_ic_observations(
    observations: tuple[CrossSectionalICObservation, ...], identity: CohortIdentity
) -> None:
    for item in observations:
        if (
            item.factor_version != identity.factor_version
            or item.outcome_horizon != identity.outcome_horizon
            or item.universe != identity.universe
            or item.benchmark != identity.benchmark
            or not identity.date_start <= item.as_of <= identity.date_end
        ):
            raise ValueError("cross-sectional IC observations do not belong to cohort")


def _identity_without_horizon(identity: CohortIdentity) -> tuple[object, ...]:
    return (
        identity.factor_version,
        identity.universe,
        identity.rebalance_cadence,
        identity.base_currency,
        identity.benchmark,
    )


def _spearman(left: tuple[float, ...], right: tuple[float, ...]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_ranks, right_ranks = _average_ranks(left), _average_ranks(right)
    return _pearson(left_ranks, right_ranks)


def _average_ranks(values: tuple[float, ...]) -> tuple[float, ...]:
    ranked = sorted(enumerate(values), key=lambda pair: (pair[1], pair[0]))
    ranks = [0.0] * len(values)
    index = 0
    while index < len(ranked):
        end = index + 1
        while end < len(ranked) and ranked[end][1] == ranked[index][1]:
            end += 1
        average = (index + 1 + end) / 2.0
        for position in range(index, end):
            ranks[ranked[position][0]] = average
        index = end
    return tuple(ranks)


def _pearson(left: tuple[float, ...], right: tuple[float, ...]) -> float | None:
    left_mean, right_mean = float(mean(left)), float(mean(right))
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    left_scale = sum((a - left_mean) ** 2 for a in left)
    right_scale = sum((b - right_mean) ** 2 for b in right)
    if left_scale == 0 or right_scale == 0:
        return None
    return float(numerator / (left_scale * right_scale) ** 0.5)


# Descriptive aliases for callers that prefer verb-oriented names.
cross_sectional_ic = calculate_cross_sectional_ic
ic_stability = summarize_ic_stability
ic_decay = calculate_ic_decay
