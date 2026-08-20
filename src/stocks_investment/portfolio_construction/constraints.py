"""Deterministic portfolio-constraint evaluation and application.

This module is deliberately pure.  It works on ticker-keyed weights and never
infers sectors, fetches data, or silently repairs an infeasible request.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite
from typing import Mapping, cast

from stocks_investment.domain import (
    ConstraintEvaluation,
    ConstraintStatus,
    PortfolioConstraint,
    PortfolioConstraintKind,
    Ticker,
)

_EPSILON = 1e-10


@dataclass(frozen=True, slots=True)
class ConstraintApplication:
    """Result of applying constraints to proposed ticker-keyed weights."""

    weights: dict[str, float]
    cash_weight: float
    evaluations: tuple[ConstraintEvaluation, ...]
    feasible: bool
    notes: tuple[str, ...] = ()


def _symbol(value: str | Ticker) -> str:
    return value.symbol if isinstance(value, Ticker) else value.strip().upper()


def _normalise(weights: Mapping[str | Ticker, float]) -> dict[str, float]:
    result: dict[str, float] = {}
    for ticker, weight in weights.items():
        symbol = _symbol(ticker)
        if not symbol:
            raise ValueError("ticker identity is required")
        if symbol in result:
            raise ValueError(f"duplicate ticker identity: {symbol}")
        if not isfinite(weight):
            raise ValueError(f"weight for {symbol} must be finite")
        result[symbol] = float(weight)
    return dict(sorted(result.items()))


def _current(current: Mapping[str | Ticker, float] | None) -> dict[str, float]:
    return _normalise(current or {})


def _sector_weight(weights: Mapping[str, float], sector: str, sectors: Mapping[str, str]) -> float | None:
    total = 0.0
    for ticker, weight in weights.items():
        if ticker not in sectors and weight > _EPSILON:
            return None
        if sectors.get(ticker) == sector:
            total += weight
    return total


def evaluate_constraints(
    weights: Mapping[str | Ticker, float],
    constraints: tuple[PortfolioConstraint, ...],
    *,
    current_weights: Mapping[str | Ticker, float] | None = None,
    sector_map: Mapping[str | Ticker, str] | None = None,
) -> tuple[ConstraintEvaluation, ...]:
    """Evaluate all constraints without modifying the supplied weights."""

    proposed = _normalise(weights)
    current = _current(current_weights)
    sectors = {_symbol(ticker): sector for ticker, sector in (sector_map or {}).items()}
    evaluations: list[ConstraintEvaluation] = []
    for constraint in constraints:
        kind = constraint.kind
        limit: float | None = constraint.limit
        scope = constraint.scope
        if kind is PortfolioConstraintKind.LONG_ONLY:
            negative = min(proposed.values(), default=0.0)
            status = ConstraintStatus.SATISFIED if negative >= -_EPSILON else ConstraintStatus.VIOLATED
            evaluations.append(ConstraintEvaluation(kind, scope, negative, limit, status,
                                                     "all proposed weights are non-negative"
                                                     if status is ConstraintStatus.SATISFIED
                                                     else "a proposed weight is negative"))
        elif kind is PortfolioConstraintKind.MAX_POSITION_WEIGHT:
            observed = max(proposed.values(), default=0.0)
            status = _bounded_status(observed, limit)
            evaluations.append(ConstraintEvaluation(kind, scope, observed, limit, status,
                                                     f"maximum position weight is {observed:.12g}"))
        elif kind is PortfolioConstraintKind.MIN_CASH_WEIGHT:
            observed = 1.0 - sum(proposed.values())
            if limit is None:
                status = ConstraintStatus.NOT_EVALUATED
            elif isclose(observed, limit, abs_tol=_EPSILON):
                status = ConstraintStatus.BINDING
            else:
                status = ConstraintStatus.SATISFIED if observed >= limit - _EPSILON else ConstraintStatus.VIOLATED
            evaluations.append(ConstraintEvaluation(kind, scope, observed, limit, status,
                                                     f"cash residual is {observed:.12g}"))
        elif kind is PortfolioConstraintKind.MAX_SECTOR_WEIGHT:
            sector_observed = _sector_weight(proposed, scope or "", sectors)
            if sector_observed is None:
                evaluations.append(ConstraintEvaluation(kind, scope, None, limit,
                                                         ConstraintStatus.NOT_EVALUATED,
                                                         "sector classification is missing for at least one ticker"))
            else:
                status = _bounded_status(sector_observed, limit)
                evaluations.append(ConstraintEvaluation(kind, scope, sector_observed, limit, status,
                                                         f"sector weight for {scope} is {sector_observed:.12g}"))
        elif kind is PortfolioConstraintKind.MAX_TURNOVER:
            observed = _turnover(proposed, current)
            status = _bounded_status(observed, limit)
            evaluations.append(ConstraintEvaluation(kind, scope, observed, limit,
                                                     status, f"gross weight turnover is {observed:.12g}"))
        else:  # pragma: no cover - defensive for future enum values
            evaluations.append(ConstraintEvaluation(kind, scope, None, limit,
                                                     ConstraintStatus.NOT_EVALUATED,
                                                     "constraint kind is unsupported"))
    return tuple(evaluations)


def _bounded_status(observed: float, limit: float | None, *, lower: bool = False) -> ConstraintStatus:
    if limit is None:
        return ConstraintStatus.NOT_EVALUATED
    if lower:
        delta = observed
        binding = isclose(delta, limit, abs_tol=_EPSILON)
        return ConstraintStatus.BINDING if binding else (
            ConstraintStatus.SATISFIED if observed >= limit - _EPSILON else ConstraintStatus.VIOLATED
        )
    binding = isclose(observed, limit, abs_tol=_EPSILON)
    return ConstraintStatus.BINDING if binding else (
        ConstraintStatus.SATISFIED if observed <= limit + _EPSILON else ConstraintStatus.VIOLATED
    )


def _turnover(proposed: Mapping[str, float], current: Mapping[str, float]) -> float:
    symbols = set(proposed) | set(current)
    return sum(abs(proposed.get(symbol, 0.0) - current.get(symbol, 0.0)) for symbol in symbols)


def apply_constraints(
    weights: Mapping[str | Ticker, float],
    constraints: tuple[PortfolioConstraint, ...],
    *,
    current_weights: Mapping[str | Ticker, float] | None = None,
    sector_map: Mapping[str | Ticker, str] | None = None,
) -> ConstraintApplication:
    """Apply transparent caps and return an explicit infeasible result when needed.

    The application algorithm first rejects negative weights, scales an
    over-budget proposal to the allowed risky budget, then repeatedly caps the
    most constrained position and redistributes its excess proportionally among
    eligible positions.  It never changes a proposal to evade a turnover cap or
    missing sector data; those cases remain infeasible.
    """

    proposed = _normalise(weights)
    current = _current(current_weights)
    sectors = {_symbol(ticker): sector for ticker, sector in (sector_map or {}).items()}
    if any(weight < -_EPSILON for weight in proposed.values()):
        return _failure(proposed, constraints, current, sectors, "negative weights violate long-only semantics")

    long_only = any(item.kind is PortfolioConstraintKind.LONG_ONLY for item in constraints)
    if not long_only and any(weight < 0 for weight in proposed.values()):
        return _failure(proposed, constraints, current, sectors, "negative weights require an explicit long-only policy")

    min_cash = max((item.limit or 0.0 for item in constraints if item.kind is PortfolioConstraintKind.MIN_CASH_WEIGHT), default=0.0)
    budget = 1.0 - min_cash
    total = sum(proposed.values())
    if total > budget + _EPSILON:
        if total <= _EPSILON:
            return _failure(proposed, constraints, current, sectors, "positive investable budget cannot be allocated")
        proposed = {symbol: weight * budget / total for symbol, weight in proposed.items()}

    position_limits = [item.limit for item in constraints if item.kind is PortfolioConstraintKind.MAX_POSITION_WEIGHT and item.limit is not None]
    max_position = min(position_limits) if position_limits else None
    sector_limits = {item.scope: item.limit for item in constraints if item.kind is PortfolioConstraintKind.MAX_SECTOR_WEIGHT and item.limit is not None}
    if sector_limits and any(symbol not in sectors for symbol, weight in proposed.items() if weight > _EPSILON):
        return _failure(proposed, constraints, current, sectors, "sector cap requires a sector for every invested ticker")

    if max_position is not None or sector_limits:
        if not _redistribute_caps(proposed, max_position, sector_limits, sectors, budget):
            return _failure(proposed, constraints, current, sectors, "position or sector caps are jointly infeasible")

    evaluations = evaluate_constraints(
        cast(Mapping[str | Ticker, float], proposed),
        constraints,
        current_weights=cast(Mapping[str | Ticker, float], current),
        sector_map=cast(Mapping[str | Ticker, str], sectors),
    )
    if any(item.status in (ConstraintStatus.VIOLATED, ConstraintStatus.NOT_EVALUATED) for item in evaluations):
        return ConstraintApplication(proposed, 1.0 - sum(proposed.values()), evaluations, False,
                                     ("constraints remain violated or unevaluable; no silent relaxation was applied",))
    return ConstraintApplication(proposed, 1.0 - sum(proposed.values()), evaluations, True,
                                 ("weights were deterministically capped/redistributed where required",))


def _redistribute_caps(weights: dict[str, float], max_position: float | None,
                       sector_limits: Mapping[str | None, float], sectors: Mapping[str, str],
                       budget: float) -> bool:
    for _ in range(len(weights) * 4 + 1):
        excess = 0.0
        for symbol in tuple(weights):
            cap = max_position
            sector = sectors.get(symbol)
            if sector in sector_limits:
                sector_total = sum(weight for name, weight in weights.items() if sectors.get(name) == sector)
                sector_cap = sector_limits[sector]
                if sector_cap is not None:
                    cap = min(cap, sector_cap - (sector_total - weights[symbol])) if cap is not None else sector_cap - (sector_total - weights[symbol])
            if cap is not None and weights[symbol] > cap + _EPSILON:
                excess += weights[symbol] - max(cap, 0.0)
                weights[symbol] = max(cap, 0.0)
        if excess <= _EPSILON:
            return sum(weights.values()) <= budget + _EPSILON
        candidates = [name for name, weight in weights.items() if weight > _EPSILON and (max_position is None or weight < max_position - _EPSILON)]
        if sector_limits:
            candidates = [name for name in candidates if sectors.get(name) not in sector_limits or sum(weight for item, weight in weights.items() if sectors.get(item) == sectors.get(name)) < sector_limits[sectors[name]] - _EPSILON]
        if not candidates:
            return False
        capacity = {name: (max_position - weights[name] if max_position is not None else float("inf")) for name in candidates}
        for name in candidates:
            sector = sectors.get(name)
            if sector in sector_limits:
                capacity[name] = min(capacity[name], sector_limits[sector] - sum(weight for item, weight in weights.items() if sectors.get(item) == sector))
        unbounded = tuple(name for name, value in capacity.items() if not isfinite(value))
        if unbounded:
            share = excess / len(unbounded)
            for name in sorted(unbounded):
                weights[name] += share
            continue
        available = sum(max(value, 0.0) for value in capacity.values())
        if available + _EPSILON < excess:
            return False
        for name in sorted(candidates):
            addition = excess * max(capacity[name], 0.0) / available
            weights[name] += addition
    return False


def _failure(weights: dict[str, float], constraints: tuple[PortfolioConstraint, ...], current: Mapping[str, float], sectors: Mapping[str, str], note: str) -> ConstraintApplication:
    return ConstraintApplication(weights, 1.0 - sum(weights.values()),
                                evaluate_constraints(
                                    cast(Mapping[str | Ticker, float], weights),
                                    constraints,
                                    current_weights=cast(Mapping[str | Ticker, float], current),
                                    sector_map=cast(Mapping[str | Ticker, str], sectors),
                                ),
                                False, (note,))
