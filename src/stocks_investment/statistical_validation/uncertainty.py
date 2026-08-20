"""Deterministic bootstrap uncertainty estimates for dated observations.

The functions in this module are deliberately small and provider-independent.
Dates define the order of the supplied observations; the statistic operates on
the corresponding numeric values.  A moving-block resample keeps the order of
each sampled contiguous block, which makes it suitable for preserving short
range temporal dependence without claiming a full time-series model.
"""

from __future__ import annotations

from datetime import date
from math import isfinite
import random
from typing import Callable, Sequence

from stocks_investment.domain.statistical_validation import BootstrapMethod, ConfidenceInterval


Statistic = Callable[[Sequence[float]], float]
DatedStatistic = tuple[date, float]


def arithmetic_mean(values: Sequence[float]) -> float:
    """Return the arithmetic mean, rejecting an empty resample."""
    if not values:
        raise ValueError("a statistic requires at least one value")
    return sum(values) / len(values)


def bootstrap_confidence_interval(
    observations: Sequence[DatedStatistic],
    *,
    statistic: Statistic = arithmetic_mean,
    method: BootstrapMethod = BootstrapMethod.IID,
    confidence_level: float,
    resamples: int,
    seed: int,
    block_size: int | None = None,
) -> ConfidenceInterval:
    """Estimate a percentile bootstrap confidence interval.

    ``observations`` must be strictly date-ordered and contain finite values.
    IID resampling draws individual values with replacement.  Moving-block
    resampling draws contiguous blocks from the ordered series until the
    original sample length is reached, then truncates the final block.

    The statistic is evaluated on numeric values in the resampled order.  It
    must return one finite real number for the original sample and every
    resample.  This function reports uncertainty only; it does not calculate
    p-values or imply statistical significance.
    """
    values = _validate_inputs(
        observations,
        method=method,
        confidence_level=confidence_level,
        resamples=resamples,
        seed=seed,
        block_size=block_size,
    )
    estimate = _evaluate(statistic, values, "original statistic")
    rng = random.Random(seed)
    bootstrap_statistics = tuple(
        _evaluate(statistic, _resample(values, method, rng, block_size), "bootstrap statistic")
        for _ in range(resamples)
    )
    alpha = (1.0 - confidence_level) / 2.0
    lower = _percentile(bootstrap_statistics, alpha)
    upper = _percentile(bootstrap_statistics, 1.0 - alpha)
    # The frozen domain contract requires the reported interval to contain
    # the sample estimate.  A finite bootstrap sample can otherwise produce
    # a one-sided percentile interval by chance, especially for tiny samples.
    lower = min(lower, estimate)
    upper = max(upper, estimate)
    return ConfidenceInterval(
        estimate=estimate,
        lower=lower,
        upper=upper,
        confidence_level=confidence_level,
        method=method,
        resamples=resamples,
        block_size=block_size,
    )


def iid_bootstrap_confidence_interval(
    observations: Sequence[DatedStatistic],
    *,
    statistic: Statistic = arithmetic_mean,
    confidence_level: float,
    resamples: int,
    seed: int,
) -> ConfidenceInterval:
    """Convenience wrapper for an IID percentile bootstrap."""
    return bootstrap_confidence_interval(
        observations,
        statistic=statistic,
        method=BootstrapMethod.IID,
        confidence_level=confidence_level,
        resamples=resamples,
        seed=seed,
    )


def moving_block_bootstrap_confidence_interval(
    observations: Sequence[DatedStatistic],
    *,
    block_size: int,
    statistic: Statistic = arithmetic_mean,
    confidence_level: float,
    resamples: int,
    seed: int,
) -> ConfidenceInterval:
    """Convenience wrapper for a moving-block percentile bootstrap."""
    return bootstrap_confidence_interval(
        observations,
        statistic=statistic,
        method=BootstrapMethod.MOVING_BLOCK,
        confidence_level=confidence_level,
        resamples=resamples,
        seed=seed,
        block_size=block_size,
    )


def _validate_inputs(
    observations: Sequence[DatedStatistic],
    *,
    method: BootstrapMethod,
    confidence_level: float,
    resamples: int,
    seed: int,
    block_size: int | None,
) -> tuple[float, ...]:
    if len(observations) < 2:
        raise ValueError("bootstrap requires at least two dated observations")
    if not isinstance(method, BootstrapMethod):
        raise TypeError("method must be a BootstrapMethod")
    if not isfinite(confidence_level) or not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be finite and between 0 and 1")
    if isinstance(resamples, bool) or not isinstance(resamples, int) or resamples <= 0:
        raise ValueError("resamples must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")

    values: list[float] = []
    previous_date: date | None = None
    for observation_date, value in observations:
        if not isinstance(observation_date, date):
            raise TypeError("observations must contain date values")
        if previous_date is not None and observation_date <= previous_date:
            raise ValueError("observations must be strictly ordered by date")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not isfinite(value):
            raise ValueError("observations must contain finite numeric values")
        previous_date = observation_date
        values.append(float(value))

    if method is BootstrapMethod.IID:
        if block_size is not None:
            raise ValueError("block_size is only valid for moving-block bootstrap")
    elif block_size is None or isinstance(block_size, bool) or not isinstance(block_size, int):
        raise ValueError("moving-block bootstrap requires a positive integer block_size")
    elif not 1 <= block_size <= len(values):
        raise ValueError("block_size must be between 1 and the sample size")
    return tuple(values)


def _resample(
    values: tuple[float, ...],
    method: BootstrapMethod,
    rng: random.Random,
    block_size: int | None,
) -> tuple[float, ...]:
    if method is BootstrapMethod.IID:
        return tuple(values[rng.randrange(len(values))] for _ in values)
    assert block_size is not None
    starts = len(values) - block_size + 1
    sample: list[float] = []
    while len(sample) < len(values):
        start = rng.randrange(starts)
        sample.extend(values[start : start + block_size])
    return tuple(sample[: len(values)])


def _evaluate(statistic: Statistic, values: Sequence[float], label: str) -> float:
    try:
        result = statistic(values)
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise ValueError(f"{label} could not be evaluated") from exc
    if isinstance(result, bool) or not isinstance(result, (int, float)) or not isfinite(result):
        raise ValueError(f"{label} must return a finite numeric value")
    return float(result)


def _percentile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    fraction = position - lower_index
    return ordered[lower_index] + fraction * (ordered[upper_index] - ordered[lower_index])


__all__ = [
    "DatedStatistic",
    "Statistic",
    "arithmetic_mean",
    "bootstrap_confidence_interval",
    "iid_bootstrap_confidence_interval",
    "moving_block_bootstrap_confidence_interval",
]
