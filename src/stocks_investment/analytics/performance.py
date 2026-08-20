"""Dependency-free portfolio time-series analytics."""

from __future__ import annotations

from math import sqrt
from datetime import date
from typing import Sequence


def simple_returns(values: Sequence[float]) -> tuple[float, ...]:
    if len(values) < 2:
        return ()
    return tuple((current / previous) - 1.0 for previous, current in zip(values, values[1:]) if previous != 0)


def time_weighted_return(values: Sequence[float], external_cash_flows: Sequence[float] | None = None) -> float:
    """Return chained subperiod return; flows are positive contributions at boundaries."""
    if len(values) < 2:
        return 0.0
    flows = external_cash_flows or (0.0,) * len(values)
    if len(flows) != len(values):
        raise ValueError("cash-flow series must align with values")
    growth = 1.0
    for previous, current, flow in zip(values, values[1:], flows[1:]):
        if previous == 0:
            continue
        growth *= (current - flow) / previous
    return growth - 1.0


def xirr(cash_flows: Sequence[tuple[object, float]], *, guess: float = 0.1) -> float:
    """Solve annualized money-weighted return with Newton iterations."""
    from datetime import date
    if not cash_flows or not any(amount < 0 for _, amount in cash_flows) or not any(amount > 0 for _, amount in cash_flows):
        raise ValueError("XIRR requires both cash outflows and inflows")
    origin = cash_flows[0][0]
    if not isinstance(origin, date):
        raise TypeError("cash-flow dates must be date instances")
    rate = guess
    for _ in range(100):
        f = 0.0
        derivative = 0.0
        for when, amount in cash_flows:
            if not isinstance(when, date):
                raise TypeError("cash-flow dates must be date instances")
            years = (when - origin).days / 365.0
            base = (1.0 + rate) ** years
            f += amount / base
            if rate > -1:
                derivative -= years * amount / ((1.0 + rate) ** (years + 1.0))
        if abs(f) < 1e-10:
            return rate
        if derivative == 0:
            break
        next_rate = rate - f / derivative
        if next_rate <= -0.999999:
            next_rate = (rate - 0.999999) / 2
        if abs(next_rate - rate) < 1e-10:
            return next_rate
        rate = next_rate
    raise ValueError("XIRR did not converge")


def maximum_drawdown(values: Sequence[float]) -> float:
    peak = None
    worst = 0.0
    for value in values:
        peak = value if peak is None else max(peak, value)
        if peak:
            worst = min(worst, value / peak - 1.0)
    return worst


def analyze_returns(values: Sequence[float], periods_per_year: int = 252) -> dict[str, float]:
    returns = simple_returns(values)
    if not returns:
        return {"total_return": 0.0, "volatility": 0.0, "max_drawdown": 0.0}
    mean = sum(returns) / len(returns)
    variance = sum((item - mean) ** 2 for item in returns) / max(1, len(returns) - 1)
    downside = [min(item, 0.0) ** 2 for item in returns]
    return {
        "total_return": values[-1] / values[0] - 1.0 if values[0] else 0.0,
        "volatility": sqrt(variance) * sqrt(periods_per_year),
        "sharpe": mean / sqrt(variance) * sqrt(periods_per_year) if variance else 0.0,
        "sortino": mean / sqrt(sum(downside) / len(downside)) * sqrt(periods_per_year) if any(downside) else 0.0,
        "max_drawdown": maximum_drawdown(values),
    }


def dated_returns(values: Sequence[tuple[date, float]]) -> dict[date, float]:
    """Calculate returns keyed by their ending date."""
    ordered = sorted(values)
    return {current_date: current_value / previous_value - 1.0
            for (previous_date, previous_value), (current_date, current_value)
            in zip(ordered, ordered[1:]) if previous_value != 0}


def aligned_return_pairs(
    portfolio: Sequence[tuple[date, float]],
    benchmark: Sequence[tuple[date, float]],
) -> tuple[tuple[float, float], ...]:
    """Join return series by ending date, never by positional index."""
    portfolio_returns = dated_returns(portfolio)
    benchmark_returns = dated_returns(benchmark)
    return tuple((portfolio_returns[when], benchmark_returns[when])
                 for when in sorted(portfolio_returns.keys() & benchmark_returns.keys()))


def beta(
    portfolio: Sequence[tuple[date, float]],
    benchmark: Sequence[tuple[date, float]],
) -> float | None:
    """Covariance(portfolio, benchmark) / variance(benchmark), date-aligned."""
    pairs = aligned_return_pairs(portfolio, benchmark)
    if len(pairs) < 2:
        return None
    portfolio_mean = sum(item[0] for item in pairs) / len(pairs)
    benchmark_mean = sum(item[1] for item in pairs) / len(pairs)
    variance = sum((market - benchmark_mean) ** 2 for _, market in pairs)
    if variance == 0:
        return None
    covariance = sum((owned - portfolio_mean) * (market - benchmark_mean) for owned, market in pairs)
    return covariance / variance


def alpha(
    portfolio: Sequence[tuple[date, float]],
    benchmark: Sequence[tuple[date, float]],
    *,
    risk_free_rate: float = 0.0,
) -> float | None:
    """CAPM arithmetic alpha: Rp - [Rf + beta * (Rm - Rf)].

    V1 uses the arithmetic mean of date-aligned periodic returns and a zero
    default risk-free rate. The caller may supply a periodic rate matching the
    input series; no implicit annualization is performed.
    """
    pairs = aligned_return_pairs(portfolio, benchmark)
    coefficient = beta(portfolio, benchmark)
    if not pairs or coefficient is None:
        return None
    portfolio_return = sum(item[0] for item in pairs) / len(pairs)
    benchmark_return = sum(item[1] for item in pairs) / len(pairs)
    return portfolio_return - (risk_free_rate + coefficient * (benchmark_return - risk_free_rate))


def benchmark_relative_return(
    portfolio: Sequence[tuple[date, float]],
    benchmark: Sequence[tuple[date, float]],
) -> float | None:
    """Difference between aligned total returns over common endpoints."""
    if not portfolio or not benchmark:
        return None
    portfolio_rows = dict(portfolio)
    benchmark_rows = dict(benchmark)
    common = sorted(set(portfolio_rows) & set(benchmark_rows))
    if len(common) < 2 or portfolio_rows[common[0]] == 0 or benchmark_rows[common[0]] == 0:
        return None
    return (portfolio_rows[common[-1]] / portfolio_rows[common[0]] - 1.0) - (benchmark_rows[common[-1]] / benchmark_rows[common[0]] - 1.0)
