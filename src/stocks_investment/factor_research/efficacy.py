"""D4 factor efficacy calculations; no factor recomputation."""

from __future__ import annotations

from statistics import mean, median
from stocks_investment.domain.research_intelligence import (
    CohortIdentity,
    FactorEfficacySummary,
    FactorOutcomeObservation,
)


def summarize_factor(
    observations: tuple[FactorOutcomeObservation, ...],
    cohort: CohortIdentity,
    *,
    quantiles: int = 5,
) -> FactorEfficacySummary:
    incompatible = tuple(
        item
        for item in observations
        if item.factor_version != cohort.factor_version
        or item.horizon != cohort.outcome_horizon
        or item.universe != cohort.universe
        or item.benchmark != cohort.benchmark
        or item.base_currency != cohort.base_currency
        or item.rebalance_cadence != cohort.rebalance_cadence
        or not cohort.date_start <= item.as_of <= cohort.date_end
    )
    if incompatible:
        raise ValueError("factor observations do not belong to the requested cohort")
    eligible = tuple(
        item
        for item in observations
        if item.factor_score is not None and item.excess_return is not None
    )
    coverage = len(eligible) / len(observations) if observations else 0.0
    if not eligible:
        return FactorEfficacySummary(
            cohort.factor_version,
            cohort.factor_version,
            cohort,
            0,
            coverage,
            metadata={"status": "insufficient_data"},
        )
    ordered = sorted(eligible, key=lambda item: (item.factor_score or 0, item.ticker.symbol))
    if len(ordered) < quantiles:
        return FactorEfficacySummary(
            eligible[0].factor_name,
            eligible[0].factor_version,
            cohort,
            len(eligible),
            coverage,
            metadata={"status": "insufficient_sample", "required_quantiles": quantiles},
        )
    qsize = max(1, len(ordered) // quantiles)
    bottom = ordered[:qsize]
    top = ordered[-qsize:]
    excess = [item.excess_return for item in eligible if item.excess_return is not None]
    top_mean = mean(item.excess_return for item in top if item.excess_return is not None)
    bottom_mean = mean(item.excess_return for item in bottom if item.excess_return is not None)
    scores = tuple(item.factor_score for item in eligible if item.factor_score is not None)
    returns = tuple(item.excess_return for item in eligible if item.excess_return is not None)
    return FactorEfficacySummary(
        eligible[0].factor_name,
        eligible[0].factor_version,
        cohort,
        len(eligible),
        coverage,
        mean(item.security_return for item in eligible if item.security_return is not None),
        mean(excess),
        median(excess),
        top_mean,
        bottom_mean,
        top_mean - bottom_mean,
        _rank_ic(scores, returns),
        sum(item > 0 for item in excess) / len(excess),
        {"quantiles": quantiles, "overlapping_horizons_may_not_be_independent": True},
    )


def _rank_ic(scores: tuple[float, ...], returns: tuple[float, ...]) -> float | None:
    if len(scores) < 2 or len(scores) != len(returns):
        return None
    sr, rr = _ranks(scores), _ranks(returns)
    n = len(sr)
    d2 = sum((a - b) ** 2 for a, b in zip(sr, rr))
    return 1 - 6 * d2 / (n * (n * n - 1))


def _ranks(values: tuple[float, ...]) -> tuple[float, ...]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    for rank, (index, _) in enumerate(ordered, 1):
        ranks[index] = float(rank)
    return tuple(ranks)
