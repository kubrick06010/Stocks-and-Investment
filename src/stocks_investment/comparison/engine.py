"""D3 deterministic strategy agreement metrics."""

from __future__ import annotations

from math import pow

from stocks_investment.analytics import analyze_returns
from stocks_investment.backtesting.engine import BacktestRun
from stocks_investment.domain.research import ResearchResult, ResearchRun
from stocks_investment.domain.research_intelligence import StrategyComparison


def compare_rankings(
    strategy_a: tuple[ResearchRun, tuple[ResearchResult, ...]],
    strategy_b: tuple[ResearchRun, tuple[ResearchResult, ...]],
    *,
    top_n: int,
) -> StrategyComparison:
    run_a, results_a = strategy_a
    run_b, results_b = strategy_b
    mismatches: list[str] = []
    if run_a.universe_name != run_b.universe_name:
        mismatches.append("universe")
    if run_a.as_of != run_b.as_of:
        mismatches.append("as_of")
    if run_a.strategy_name == run_b.strategy_name and run_a.strategy_version != run_b.strategy_version:
        mismatches.append("strategy_version")
    top_a = {
        item.ticker.symbol
        for item in sorted(
            (x for x in results_a if x.rank is not None),
            key=lambda x: (x.rank or 0, x.ticker.symbol),
        )[:top_n]
    }
    top_b = {
        item.ticker.symbol
        for item in sorted(
            (x for x in results_b if x.rank is not None),
            key=lambda x: (x.rank or 0, x.ticker.symbol),
        )[:top_n]
    }
    union = top_a | top_b
    intersection = top_a & top_b
    jaccard = len(intersection) / len(union) if union else None
    agreement = len(intersection) / top_n if top_n else None
    ranks_a = {x.ticker.symbol: x.rank for x in results_a if x.rank is not None}
    ranks_b = {x.ticker.symbol: x.rank for x in results_b if x.rank is not None}
    common = sorted(ranks_a.keys() & ranks_b.keys())
    rank_correlation = (
        _spearman(tuple(ranks_a[s] for s in common), tuple(ranks_b[s] for s in common))
        if len(common) >= 2
        else None
    )
    return StrategyComparison(
        run_a.strategy_name,
        run_b.strategy_name,
        min(run_a.as_of, run_b.as_of),
        max(run_a.as_of, run_b.as_of),
        run_a.universe_name,
        (run_a.id, run_b.id),
        agreement,
        rank_correlation,
        agreement,
        assumption_mismatches=tuple(mismatches),
        metadata={"jaccard": jaccard, "strategy_versions": (run_a.strategy_version, run_b.strategy_version)},
    )


def compare_backtests(left: BacktestRun, right: BacktestRun) -> StrategyComparison:
    """Compare immutable C6 simulations without rerunning either strategy."""
    mismatches: list[str] = []
    details: list[dict[str, object]] = []

    def check(field: str, a: object, b: object) -> None:
        if a != b:
            mismatches.append(field)
            details.append({"field": field, "strategy_a": a, "strategy_b": b})

    check("period", (left.config.start, left.config.end), (right.config.start, right.config.end))
    check("benchmark", left.config.benchmark, right.config.benchmark)
    check("universe", left.config.universe, right.config.universe)
    check("rebalance_frequency", left.config.rebalance_frequency, right.config.rebalance_frequency)
    check("selection_rule", left.config.selection_rule, right.config.selection_rule)
    check("top_n", left.config.top_n, right.config.top_n)
    check("weighting_method", left.config.weighting_method, right.config.weighting_method)
    check("transaction_cost_model", left.config.transaction_cost_model, right.config.transaction_cost_model)
    check("transaction_cost_rate", left.config.transaction_cost_rate, right.config.transaction_cost_rate)
    check("corporate_action_policy", left.config.corporate_action_mode, right.config.corporate_action_mode)
    check("return_convention", left.config.return_convention, right.config.return_convention)
    if left.strategy_name == right.strategy_name:
        check("strategy_version", left.strategy_version, right.strategy_version)

    def metrics(run: BacktestRun) -> dict[str, float]:
        values = [run.config.initial_capital] + [period.ending_value for period in run.periods]
        result = analyze_returns(values, periods_per_year=1)
        days = max(1, (run.config.end - run.config.start).days)
        cagr = pow(run.final_value / run.config.initial_capital, 365.25 / days) - 1.0
        benchmark = 1.0
        for period in run.periods:
            if period.benchmark_return is not None:
                benchmark *= 1.0 + period.benchmark_return
        return {
            "cumulative_return": run.total_return,
            "cagr": cagr,
            "volatility": result.get("volatility", 0.0),
            "max_drawdown": result.get("max_drawdown", 0.0),
            "sharpe": result.get("sharpe", 0.0),
            "benchmark_cumulative_return": benchmark - 1.0,
            "benchmark_excess_return": run.total_return - (benchmark - 1.0),
            "turnover": sum(period.turnover for period in run.periods),
            "transaction_costs": sum(period.transaction_cost for period in run.periods),
        }

    left_metrics, right_metrics = metrics(left), metrics(right)
    compatible = not mismatches
    return StrategyComparison(
        left.strategy_name,
        right.strategy_name,
        max(left.config.start, right.config.start),
        min(left.config.end, right.config.end),
        left.config.benchmark,
        tuple(period.research_run_id for period in left.periods) + tuple(period.research_run_id for period in right.periods),
        # Do not expose a direct winner when assumptions are incompatible.
        # Individual diagnostics remain below in metadata, explicitly marked
        # as non-comparable.
        return_a=left.total_return if compatible else None,
        return_b=right.total_return if compatible else None,
        excess_return_a=left_metrics["benchmark_excess_return"] if compatible else None,
        excess_return_b=right_metrics["benchmark_excess_return"] if compatible else None,
        turnover_a=left_metrics["turnover"] if compatible else None,
        turnover_b=right_metrics["turnover"] if compatible else None,
        assumption_mismatches=tuple(mismatches),
        metadata={
            "compatible": compatible,
            "performance_comparable": compatible,
            "compatibility_details": details,
            "strategy_versions": (left.strategy_version, right.strategy_version),
            "comparison_scope": {
                "period": (left.config.start, left.config.end),
                "universe": left.config.universe,
                "benchmark": left.config.benchmark,
                "rebalance_frequency": left.config.rebalance_frequency,
                "selection_rule": left.config.selection_rule,
                "top_n": left.config.top_n,
                "weighting_method": left.config.weighting_method,
                "transaction_cost_model": left.config.transaction_cost_model,
                "transaction_cost_rate": left.config.transaction_cost_rate,
                "corporate_action_policy": left.config.corporate_action_mode,
                "return_convention": left.config.return_convention,
            },
            "performance_a": left_metrics,
            "performance_b": right_metrics,
            "gross_net_convention": "period gross_return and net_return are preserved; comparison uses net_return/final_value",
        },
    )


def _spearman(left: tuple[int, ...], right: tuple[int, ...]) -> float:
    n = len(left)
    d2 = sum((a - b) ** 2 for a, b in zip(left, right))
    return 1 - (6 * d2) / (n * (n * n - 1)) if n > 1 else 1.0
