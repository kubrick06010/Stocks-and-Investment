"""Deterministic regime slices and turnover-adjusted factor diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite
from statistics import mean, median
from typing import Iterable, Mapping

from stocks_investment.domain.research_intelligence import FactorOutcomeObservation
from stocks_investment.domain.statistical_validation import StatisticalStatus

ObservationKey = tuple[str, date]


@dataclass(frozen=True, slots=True)
class RobustnessSlice:
    label: str
    eligible_observations: int
    usable_observations: int
    coverage: float
    mean_excess_return: float | None
    median_excess_return: float | None
    rank_association: float | None
    status: StatisticalStatus


@dataclass(frozen=True, slots=True)
class RobustnessSummary:
    factor_name: str
    factor_version: str
    universe: str
    horizon: str
    benchmark: str
    base_currency: str
    eligible_observations: int
    labelled_observations: int
    slices: tuple[RobustnessSlice, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TurnoverAdjustedEfficacy:
    gross_spread: float
    gross_traded_notional: float
    portfolio_capital: float
    turnover: float
    transaction_cost_rate: float
    transaction_cost: float
    cost_return_impact: float
    net_spread: float
    methodology_version: str = "turnover_adjusted_efficacy_v1"


def summarize_explicit_slices(
    observations: Iterable[FactorOutcomeObservation],
    labels: Mapping[ObservationKey, str],
    *,
    minimum_sample_size: int = 5,
) -> RobustnessSummary:
    """Summarize pre-labelled year/regime slices without inferring regimes.

    Labels are joined by ticker and research date. Missing labels and outcomes
    remain exclusions. Rank association is descriptive pooled Spearman within
    a slice; it is not a significance or causal estimate.
    """

    if minimum_sample_size < 2:
        raise ValueError("minimum_sample_size must be at least 2")
    rows = tuple(observations)
    if not rows:
        raise ValueError("at least one factor outcome observation is required")
    identity = _identity(rows)
    indexed: dict[ObservationKey, FactorOutcomeObservation] = {}
    for row in rows:
        key = (row.ticker.symbol, row.as_of)
        if key in indexed:
            raise ValueError(f"duplicate factor outcome identity for {key[0]} on {key[1]}")
        indexed[key] = row

    grouped: dict[str, list[FactorOutcomeObservation]] = {}
    for key, row in indexed.items():
        label = labels.get(key)
        if label is None or not label.strip():
            continue
        grouped.setdefault(label, []).append(row)

    slices: list[RobustnessSlice] = []
    for label in sorted(grouped):
        eligible = tuple(grouped[label])
        usable = tuple(
            row
            for row in eligible
            if row.factor_score is not None
            and row.excess_return is not None
            and row.outcome_status.lower() in {"valid", "measured", "available", "usable", "complete"}
        )
        coverage = len(usable) / len(eligible)
        status = (
            StatisticalStatus.VALID
            if len(usable) >= minimum_sample_size
            else StatisticalStatus.INSUFFICIENT_COVERAGE
            if len(usable) < len(eligible)
            else StatisticalStatus.INSUFFICIENT_SAMPLE
        )
        excess = tuple(row.excess_return for row in usable if row.excess_return is not None)
        scores = tuple(row.factor_score for row in usable if row.factor_score is not None)
        slices.append(
            RobustnessSlice(
                label,
                len(eligible),
                len(usable),
                coverage,
                mean(excess) if status is StatisticalStatus.VALID else None,
                median(excess) if status is StatisticalStatus.VALID else None,
                _spearman(scores, excess) if status is StatisticalStatus.VALID else None,
                status,
            )
        )
    labelled_count = sum(len(items) for items in grouped.values())
    limitations = (
        "regimes are externally labelled and were not inferred or optimized",
        "pooled slice rank association may conceal date-level instability",
        "descriptive results do not establish causality or statistical significance",
    )
    return RobustnessSummary(
        identity[0], identity[1], identity[2], identity[3], identity[4], identity[5],
        len(rows), labelled_count, tuple(slices), limitations,
    )


def turnover_adjusted_efficacy(
    gross_spread: float,
    *,
    gross_traded_notional: float,
    portfolio_capital: float,
    transaction_cost_rate: float,
) -> TurnoverAdjustedEfficacy:
    """Deduct explicit traded-notional cost impact from a gross return spread."""

    values = (gross_spread, gross_traded_notional, portfolio_capital, transaction_cost_rate)
    if not all(isfinite(value) for value in values):
        raise ValueError("turnover-adjusted efficacy inputs must be finite")
    if portfolio_capital <= 0:
        raise ValueError("portfolio_capital must be positive")
    if gross_traded_notional < 0 or transaction_cost_rate < 0:
        raise ValueError("traded notional and transaction cost rate cannot be negative")
    turnover = gross_traded_notional / portfolio_capital
    transaction_cost = gross_traded_notional * transaction_cost_rate
    cost_impact = transaction_cost / portfolio_capital
    return TurnoverAdjustedEfficacy(
        gross_spread,
        gross_traded_notional,
        portfolio_capital,
        turnover,
        transaction_cost_rate,
        transaction_cost,
        cost_impact,
        gross_spread - cost_impact,
    )


def _identity(rows: tuple[FactorOutcomeObservation, ...]) -> tuple[str, ...]:
    identities = {
        (
            row.factor_name,
            row.factor_version,
            row.universe,
            row.horizon,
            row.benchmark,
            row.base_currency,
            row.rebalance_cadence,
        )
        for row in rows
    }
    if len(identities) != 1:
        raise ValueError("robustness observations mix incompatible cohort identity")
    return next(iter(identities))


def _spearman(left: tuple[float, ...], right: tuple[float, ...]) -> float | None:
    if len(left) < 2 or len(left) != len(right):
        return None
    left_ranks, right_ranks = _ranks(left), _ranks(right)
    left_mean, right_mean = mean(left_ranks), mean(right_ranks)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left_ranks, right_ranks))
    left_scale = sum((value - left_mean) ** 2 for value in left_ranks)
    right_scale = sum((value - right_mean) ** 2 for value in right_ranks)
    if left_scale == 0 or right_scale == 0:
        return None
    return float(numerator / (left_scale * right_scale) ** 0.5)


def _ranks(values: tuple[float, ...]) -> tuple[float, ...]:
    ordered = sorted(enumerate(values), key=lambda item: (item[1], item[0]))
    ranks = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][1] == ordered[start][1]:
            end += 1
        average_rank = (start + 1 + end) / 2.0
        for index in range(start, end):
            ranks[ordered[index][0]] = average_rank
        start = end
    return tuple(ranks)
