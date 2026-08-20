"""Small cross-sectional simulation foundation with explicit information barriers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Mapping, Sequence

from stocks_investment.domain.market import PriceAdjustmentPolicy
from stocks_investment.domain.research import ResearchResult, ResearchRun
from stocks_investment.domain.research_engine import PointInTimeDataView, UniverseSnapshot


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    start: date
    end: date
    top_n: int = 5
    transaction_cost: float = 0.0
    initial_cash: float = 1.0

    def __post_init__(self) -> None:
        if self.end < self.start or self.top_n <= 0 or self.transaction_cost < 0:
            raise ValueError("invalid backtest configuration")


@dataclass(frozen=True, slots=True)
class BacktestResult:
    start: date
    end: date
    values: tuple[tuple[date, float], ...]
    benchmark_return: float | None
    transaction_cost: float
    survivorship_bias_limited: bool

    @property
    def total_return(self) -> float:
        return self.values[-1][1] / self.values[0][1] - 1.0 if self.values and self.values[0][1] else 0.0


class CorporateActionMode(StrEnum):
    RAW_PRICES_EXPLICIT_ACTIONS = "raw_prices_explicit_actions"
    SPLIT_ADJUSTED_NO_ACTIONS = "split_adjusted_no_actions"
    TOTAL_RETURN_ADJUSTED_NO_DIVIDENDS = "total_return_adjusted_no_dividends"


@dataclass(frozen=True, slots=True)
class BacktestConfigV1:
    start: date
    end: date
    top_n: int
    initial_capital: float
    transaction_cost_rate: float
    benchmark: str
    corporate_action_mode: CorporateActionMode = CorporateActionMode.RAW_PRICES_EXPLICIT_ACTIONS
    weighting_method: str = "equal_weight"
    selection_rule: str = "top_n_by_persisted_rank"
    universe: str = "unspecified"
    rebalance_frequency: str = "research_run_schedule"
    transaction_cost_model: str = "gross_traded_notional"
    return_convention: str = "net_total_return"

    def __post_init__(self) -> None:
        if self.end <= self.start or self.top_n <= 0 or self.initial_capital <= 0:
            raise ValueError("invalid multi-period backtest configuration")
        if not 0 <= self.transaction_cost_rate < 1:
            raise ValueError("transaction cost rate must be in [0, 1)")
        if not all((self.weighting_method, self.universe, self.rebalance_frequency,
                    self.transaction_cost_model, self.return_convention)):
            raise ValueError("backtest methodology identity fields must not be empty")


@dataclass(frozen=True, slots=True)
class SecurityAttribution:
    symbol: str
    start_weight: float
    security_return: float
    contribution: float


@dataclass(frozen=True, slots=True)
class BacktestPeriod:
    period_index: int
    research_run_id: str
    rebalance_date: date
    holding_start: date
    holding_end: date
    starting_value: float
    ending_value: float
    gross_return: float
    turnover: float
    transaction_cost: float
    net_return: float
    benchmark_return: float | None
    excess_return: float | None
    selected_symbols: tuple[str, ...]
    attribution: tuple[SecurityAttribution, ...] = ()


@dataclass(frozen=True, slots=True)
class BacktestRun:
    id: str
    strategy_name: str
    strategy_version: str
    config: BacktestConfigV1
    periods: tuple[BacktestPeriod, ...]
    final_value: float
    status: str = "completed"

    @property
    def total_return(self) -> float:
        return self.final_value / self.config.initial_capital - 1.0


def rebalance_metrics(
    current_values: Mapping[str, float],
    target_weights: Mapping[str, float],
    portfolio_value: float,
    transaction_cost_rate: float,
) -> tuple[float, float, float, float]:
    """Return (traded notional, turnover, cost, investable value) by identity.

    Traded notional counts buys plus sells. Turnover is traded notional divided
    by pre-trade portfolio value; this differs from the half-absolute-weight
    convention and is recorded explicitly in the methodology.
    """
    if portfolio_value < 0 or transaction_cost_rate < 0:
        raise ValueError("portfolio value and cost rate must be non-negative")
    if abs(sum(target_weights.values()) - 1.0) > 1e-9:
        raise ValueError("target weights must sum to one")
    symbols = set(current_values) | set(target_weights)
    target_values = {symbol: portfolio_value * target_weights.get(symbol, 0.0) for symbol in symbols}
    traded = sum(abs(target_values[symbol] - current_values.get(symbol, 0.0)) for symbol in symbols)
    cost = traded * transaction_cost_rate
    return traded, traded / portfolio_value if portfolio_value else 0.0, cost, portfolio_value - cost


def _ranked_symbols(results: Sequence[ResearchResult], top_n: int) -> tuple[str, ...]:
    ranked = sorted((row for row in results if row.rank is not None), key=lambda row: (row.rank or 0, row.ticker.symbol))
    return tuple(row.ticker.symbol for row in ranked[:top_n])


def simulate_persisted_runs(
    runs: Sequence[tuple[ResearchRun, Sequence[ResearchResult]]],
    prices: Mapping[date, Mapping[str, float]],
    benchmark_prices: Mapping[date, float],
    *,
    config: BacktestConfigV1,
    universes: Mapping[tuple[str, str], UniverseSnapshot] | None = None,
) -> BacktestRun:
    """Simulate portfolios formed from frozen ResearchResult rankings.

    The backtester never evaluates a strategy. Each tuple contains an already
    persisted run identifier (or ResearchRun-like object) and its persisted
    results. Prices are keyed by date and ticker; missing observations fail
    explicitly rather than falling back to current or previous data.
    """
    if not runs:
        raise ValueError("at least one persisted research run is required")
    if config.weighting_method != "equal_weight":
        raise ValueError("the V1 simulator supports only equal_weight portfolio formation")
    ordered_runs = tuple(sorted(runs, key=lambda item: getattr(item[0], "as_of")))
    if any((run.strategy_name, run.strategy_version) !=
           (ordered_runs[0][0].strategy_name, ordered_runs[0][0].strategy_version)
           for run, _ in ordered_runs):
        raise ValueError("persisted ResearchRuns use incompatible strategy identities")
    if ordered_runs[0][0].as_of != config.start:
        raise ValueError("first persisted ResearchRun must match backtest start")
    if any(run[0].as_of < config.start or run[0].as_of >= config.end for run in ordered_runs):
        raise ValueError("research runs must lie within the backtest interval")
    capital = config.initial_capital
    holdings: dict[str, float] = {}
    periods: list[BacktestPeriod] = []
    for index, (research_run, results) in enumerate(ordered_runs):
        start = research_run.as_of
        end = ordered_runs[index + 1][0].as_of if index + 1 < len(ordered_runs) else config.end
        selected = _ranked_symbols(results, config.top_n)
        if not selected:
            raise ValueError(f"persisted ResearchRun {research_run.id} has no ranked selections")
        if universes is not None:
            if research_run.universe_version is None:
                raise ValueError(f"ResearchRun {research_run.id} lacks universe version")
            snapshot = universes.get((research_run.universe_name, research_run.universe_version))
            if snapshot is None:
                raise ValueError(f"missing universe snapshot for {research_run.id}")
            eligible = {member.symbol for member in snapshot.members}
            if any(symbol not in eligible for symbol in selected):
                raise ValueError(f"persisted result is outside its historical universe: {research_run.id}")
        start_prices = prices.get(start)
        end_prices = prices.get(end)
        if start_prices is None or end_prices is None:
            raise ValueError(f"missing price date for period {start} -> {end}")
        if any(symbol not in start_prices or symbol not in end_prices for symbol in selected):
            raise ValueError("missing price for selected security")
        current_values = {symbol: quantity * start_prices[symbol] for symbol, quantity in holdings.items()}
        pre_trade_value = capital + sum(current_values.values())
        target_weight = 1.0 / len(selected)
        target_weights = {symbol: target_weight for symbol in selected}
        traded_notional, turnover, cost, investable = rebalance_metrics(
            current_values, target_weights, pre_trade_value, config.transaction_cost_rate)
        target_pre_cost = {symbol: pre_trade_value * target_weight for symbol in selected}
        if investable < 0:
            raise ValueError("transaction costs exceed available portfolio value")
        holdings = {symbol: investable * target_weight / start_prices[symbol] for symbol in selected}
        capital = 0.0
        ending_value = sum(quantity * end_prices[symbol] for symbol, quantity in holdings.items())
        gross_end = sum(target_pre_cost[symbol] * end_prices[symbol] / start_prices[symbol] for symbol in selected)
        gross_return = gross_end / pre_trade_value - 1.0 if pre_trade_value else 0.0
        net_return = ending_value / pre_trade_value - 1.0 if pre_trade_value else 0.0
        benchmark_return = _return_for_dates(benchmark_prices, start, end)
        excess = net_return - benchmark_return if benchmark_return is not None else None
        attribution = tuple(SecurityAttribution(symbol, target_weight,
            end_prices[symbol] / start_prices[symbol] - 1.0,
            target_weight * (end_prices[symbol] / start_prices[symbol] - 1.0)) for symbol in selected)
        periods.append(BacktestPeriod(index, research_run.id, start, start, end, pre_trade_value,
                                      ending_value, gross_return, turnover, cost, net_return,
                                      benchmark_return, excess, selected, attribution))
    final_value = periods[-1].ending_value
    strategy_name = ordered_runs[0][0].strategy_name
    strategy_version = ordered_runs[0][0].strategy_version
    return BacktestRun("backtest-" + ordered_runs[0][0].id, strategy_name, strategy_version,
                       config, tuple(periods), final_value)


def _return_for_dates(prices: Mapping[date, float], start: date, end: date) -> float | None:
    if start not in prices or end not in prices or prices[start] == 0:
        return None
    return prices[end] / prices[start] - 1.0


def validate_adjustment_mode(policy: PriceAdjustmentPolicy, mode: CorporateActionMode) -> None:
    if mode is CorporateActionMode.RAW_PRICES_EXPLICIT_ACTIONS and policy is not PriceAdjustmentPolicy.RAW:
        raise ValueError("raw explicit-action mode requires RAW prices")
    if mode is CorporateActionMode.SPLIT_ADJUSTED_NO_ACTIONS and policy is PriceAdjustmentPolicy.RAW:
        raise ValueError("split-adjusted mode requires split-adjusted prices")
    if mode is CorporateActionMode.TOTAL_RETURN_ADJUSTED_NO_DIVIDENDS and policy is not PriceAdjustmentPolicy.TOTAL_RETURN_ADJUSTED:
        raise ValueError("total-return mode requires total-return-adjusted prices")


def apply_split_raw(quantity: float, price: float, numerator: int, denominator: int) -> tuple[float, float, float]:
    """Apply one raw-price split and return (new quantity, new price, wealth)."""
    if quantity < 0 or price < 0 or numerator <= 0 or denominator <= 0:
        raise ValueError("invalid split inputs")
    new_quantity = quantity * numerator / denominator
    new_price = price * denominator / numerator
    return new_quantity, new_price, quantity * price


def dividend_cash(quantity: float, amount_per_share: float, mode: CorporateActionMode) -> float:
    """Credit an explicit dividend only for raw-price action semantics."""
    if mode is CorporateActionMode.TOTAL_RETURN_ADJUSTED_NO_DIVIDENDS:
        raise ValueError("explicit dividends are forbidden with total-return prices")
    if quantity < 0 or amount_per_share < 0:
        raise ValueError("dividend inputs must be non-negative")
    return quantity * amount_per_share


def simulate_equal_weight(
    universe: UniverseSnapshot,
    data: PointInTimeDataView,
    scores_by_date: Mapping[date, Mapping[str, float]],
    *,
    config: BacktestConfig,
    benchmark_prices: Sequence[tuple[date, float]] = (),
) -> BacktestResult:
    """Form a top-N equal-weight portfolio using only the supplied PIT view.

    This intentionally accepts precomputed scores: strategy evaluation belongs
    upstream and must use the same `PointInTimeDataView` information barrier.
    """
    if data.as_of > config.start:
        raise ValueError("PIT data view cannot be newer than simulation start")
    selected = tuple(sorted(scores_by_date.get(config.start, {}), key=lambda symbol: (-scores_by_date[config.start][symbol], symbol))[:config.top_n])
    bars = {symbol: tuple(sorted((bar for bar in data.price_data if bar.ticker.symbol == symbol and config.start <= bar.session <= config.end), key=lambda bar: bar.session)) for symbol in selected}
    if any(not rows for rows in bars.values()):
        raise ValueError("selected symbols require price history")
    policies = {bar.adjustment_policy for rows in bars.values() for bar in rows}
    if len(policies) > 1:
        raise ValueError("mixed price-adjustment policies are unsupported")
    dates = sorted({bar.session for rows in bars.values() for bar in rows})
    values: list[tuple[date, float]] = []
    starts = {symbol: rows[0].close for symbol, rows in bars.items()}
    for when in dates:
        end_prices = {
            symbol: next((bar.close for bar in rows if bar.session == when), None)
            for symbol, rows in bars.items()
        }
        if any(price is None for price in end_prices.values()):
            continue
        # Keep the ticker key through the calculation. Filtering a parallel
        # price list would allow a missing middle ticker to shift identities.
        gross = sum(
            float(end_price) / float(starts[symbol])
            for symbol, end_price in end_prices.items()
            if end_price is not None
        ) / len(starts)
        # V1 models a one-time entry cost on initial capital. Keep the initial
        # mark at contributed capital, then subtract the explicit cost from
        # the gross terminal value; this makes a 10% gain with 1% entry cost
        # equal to a 9% return, not a compounded or denominator-shifted value.
        value = config.initial_cash if when == dates[0] else config.initial_cash * (gross - config.transaction_cost)
        values.append((when, value))
    benchmark_return = None
    if benchmark_prices:
        ordered = sorted(benchmark_prices)
        benchmark_return = ordered[-1][1] / ordered[0][1] - 1.0
    return BacktestResult(config.start, config.end, tuple(values), benchmark_return, config.transaction_cost,
                          UniverseSnapshot.__dataclass_fields__["limitations"].default is not None and bool(universe.limitations))


def scores_from_persisted_results(results: Sequence[ResearchResult]) -> dict[str, float]:
    """Recover a formation score map from frozen ResearchResults.

    This is intentionally a narrow bridge: the simulator consumes persisted
    decisions rather than recalculating current metrics or strategy outputs.
    """
    return {result.ticker.symbol: result.composite_score
            for result in results if result.composite_score is not None}
