from dataclasses import replace
from datetime import date, datetime, timezone
from pytest import approx

from stocks_investment.comparison import compare_backtests, compare_rankings
from stocks_investment.backtesting import BacktestConfigV1, BacktestPeriod, BacktestRun
from stocks_investment.domain import ResearchResult, ResearchRun, ResearchRunStatus, Ticker
from stocks_investment.backtesting import CorporateActionMode


def test_comparison_uses_identity_safe_overlap_and_mismatch_metadata() -> None:
    def run(identifier: str, strategy: str, when: date) -> ResearchRun:
        return ResearchRun(
            identifier,
            datetime.combine(when, datetime.min.time(), timezone.utc),
            when,
            strategy,
            "v1",
            "u",
            "u1",
            when,
            {},
            status=ResearchRunStatus.COMPLETED,
        )

    a, b = run("a", "graham", date(2025, 1, 1)), run("b", "quality", date(2025, 1, 2))
    ra = tuple(
        ResearchResult(f"a:{s}", "a", Ticker(s), a.created_at, i + 1, 80, "selected")
        for i, s in enumerate(("AAA", "BBB", "CCC"))
    )
    rb = tuple(
        ResearchResult(f"b:{s}", "b", Ticker(s), b.created_at, i + 1, 80, "selected")
        for i, s in enumerate(("AAA", "DDD", "CCC"))
    )
    result = compare_rankings((a, ra), (b, rb), top_n=2)
    assert result.top_n_overlap == 0.5
    assert result.assumption_mismatches == ("as_of",)


def test_backtest_comparison_consumes_persisted_simulation_and_exposes_costs() -> None:
    config = BacktestConfigV1(date(2024, 1, 1), date(2025, 1, 1), 2, 100.0, 0.01, "BENCH", CorporateActionMode.RAW_PRICES_EXPLICIT_ACTIONS)
    period_a = BacktestPeriod(0, "run-a", date(2024, 1, 1), date(2024, 1, 1), date(2025, 1, 1), 100, 108, .10, .4, 4, .08, .05, .03, ("AAA", "BBB"))
    period_b = BacktestPeriod(0, "run-b", date(2024, 1, 1), date(2024, 1, 1), date(2025, 1, 1), 100, 104, .06, .2, 2, .04, .05, -.01, ("AAA", "CCC"))
    left = BacktestRun("bt-a", "graham", "graham_v1", config, (period_a,), 108)
    right = BacktestRun("bt-b", "quality", "quality_v1", config, (period_b,), 104)
    comparison = compare_backtests(left, right)
    # Hand check: 108/100 - 1 = 8%, 104/100 - 1 = 4%; costs are 4 and 2.
    assert comparison.assumption_mismatches == ()
    assert comparison.return_a == approx(.08) and comparison.return_b == approx(.04)
    assert comparison.metadata["performance_a"]["transaction_costs"] == 4
    assert comparison.metadata["performance_b"]["turnover"] == .2


def test_backtest_comparison_reports_fairness_mismatches() -> None:
    base = BacktestConfigV1(date(2024, 1, 1), date(2025, 1, 1), 2, 100.0, 0.01, "BENCH")
    other = BacktestConfigV1(date(2024, 1, 1), date(2025, 1, 1), 2, 100.0, 0.02, "OTHER")
    period = BacktestPeriod(0, "r", date(2024, 1, 1), date(2024, 1, 1), date(2025, 1, 1), 100, 100, 0, 0, 0, 0, 0, 0, ("AAA",))
    left = BacktestRun("a", "s", "v1", base, (period,), 100)
    right = BacktestRun("b", "s", "v2", other, (period,), 100)
    result = compare_backtests(left, right)
    assert result.metadata["compatible"] is False
    assert set(result.assumption_mismatches) >= {"benchmark", "transaction_cost_rate", "strategy_version"}
    assert result.return_a is None and result.return_b is None
    assert result.metadata["performance_comparable"] is False


def _backtest_pair(*, right_config: BacktestConfigV1 | None = None,
                   right_version: str = "v1") -> tuple[BacktestRun, BacktestRun]:
    config = BacktestConfigV1(
        date(2024, 1, 1),
        date(2025, 1, 1),
        2,
        100.0,
        0.01,
        "BENCH",
        CorporateActionMode.RAW_PRICES_EXPLICIT_ACTIONS,
    )
    period = BacktestPeriod(
        0, "research-a", date(2024, 1, 1), date(2024, 1, 1), date(2025, 1, 1),
        100.0, 110.0, 0.10, 0.20, 2.0, 0.08, 0.05, 0.03, ("AAA", "BBB"),
    )
    other_period = replace(period, research_run_id="research-b", ending_value=105.0,
                            gross_return=0.05, transaction_cost=1.0, net_return=0.04)
    left = BacktestRun("bt-a", "balanced", "v1", config, (period,), 110.0)
    right = BacktestRun("bt-b", "balanced", right_version,
                        right_config or config, (other_period,), 105.0)
    return left, right


def _assert_only_mismatch(field: str, *, config: BacktestConfigV1 | None = None,
                          version: str = "v1") -> None:
    left, right = _backtest_pair(right_config=config, right_version=version)
    result = compare_backtests(left, right)
    assert result.assumption_mismatches == (field,)
    details = result.metadata["compatibility_details"]
    assert len(details) == 1
    assert details[0]["field"] == field
    assert "strategy_a" in details[0] and "strategy_b" in details[0]


def test_fairness_matrix_period_is_one_field_at_a_time() -> None:
    base = BacktestConfigV1(date(2024, 1, 1), date(2025, 1, 1), 2, 100.0, 0.01, "BENCH")
    _assert_only_mismatch("period", config=replace(base, end=date(2025, 2, 1)))


def test_fairness_matrix_benchmark_is_one_field_at_a_time() -> None:
    base = BacktestConfigV1(date(2024, 1, 1), date(2025, 1, 1), 2, 100.0, 0.01, "BENCH")
    _assert_only_mismatch("benchmark", config=replace(base, benchmark="OTHER"))


def test_fairness_matrix_universe_is_one_field_at_a_time() -> None:
    base = BacktestConfigV1(date(2024, 1, 1), date(2025, 1, 1), 2, 100.0, 0.01, "BENCH")
    _assert_only_mismatch("universe", config=replace(base, universe="NASDAQ@2024"))


def test_fairness_matrix_rebalance_frequency_is_one_field_at_a_time() -> None:
    base = BacktestConfigV1(date(2024, 1, 1), date(2025, 1, 1), 2, 100.0, 0.01, "BENCH")
    _assert_only_mismatch("rebalance_frequency", config=replace(base, rebalance_frequency="monthly"))


def test_fairness_matrix_selection_rule_is_one_field_at_a_time() -> None:
    base = BacktestConfigV1(date(2024, 1, 1), date(2025, 1, 1), 2, 100.0, 0.01, "BENCH")
    _assert_only_mismatch("selection_rule", config=replace(base, selection_rule="manual"))


def test_fairness_matrix_top_n_is_one_field_at_a_time() -> None:
    base = BacktestConfigV1(date(2024, 1, 1), date(2025, 1, 1), 2, 100.0, 0.01, "BENCH")
    _assert_only_mismatch("top_n", config=replace(base, top_n=3))


def test_fairness_matrix_weighting_is_one_field_at_a_time() -> None:
    base = BacktestConfigV1(date(2024, 1, 1), date(2025, 1, 1), 2, 100.0, 0.01, "BENCH")
    _assert_only_mismatch("weighting_method", config=replace(base, weighting_method="market_cap"))


def test_strategy_names_remain_distinct_without_being_a_mismatch() -> None:
    left, right = _backtest_pair()
    distinct = BacktestRun(
        right.id, "other_strategy", right.strategy_version, right.config,
        right.periods, right.final_value,
    )
    result = compare_backtests(left, distinct)
    assert result.assumption_mismatches == ()
    assert (result.strategy_a, result.strategy_b) == ("balanced", "other_strategy")
    assert result.metadata["strategy_versions"] == ("v1", "v1")


def test_fairness_matrix_transaction_cost_rate_is_one_field_at_a_time() -> None:
    base = BacktestConfigV1(date(2024, 1, 1), date(2025, 1, 1), 2, 100.0, 0.01, "BENCH")
    _assert_only_mismatch("transaction_cost_rate", config=replace(base, transaction_cost_rate=0.02))


def test_fairness_matrix_transaction_cost_model_is_one_field_at_a_time() -> None:
    base = BacktestConfigV1(date(2024, 1, 1), date(2025, 1, 1), 2, 100.0, 0.01, "BENCH")
    _assert_only_mismatch("transaction_cost_model", config=replace(base, transaction_cost_model="entry_haircut"))


def test_fairness_matrix_corporate_action_policy_is_one_field_at_a_time() -> None:
    base = BacktestConfigV1(date(2024, 1, 1), date(2025, 1, 1), 2, 100.0, 0.01, "BENCH")
    _assert_only_mismatch(
        "corporate_action_policy",
        config=replace(base, corporate_action_mode=CorporateActionMode.SPLIT_ADJUSTED_NO_ACTIONS),
    )


def test_fairness_matrix_strategy_version_is_one_field_at_a_time() -> None:
    _assert_only_mismatch("strategy_version", version="v2")


def test_fairness_matrix_return_convention_is_one_field_at_a_time() -> None:
    base = BacktestConfigV1(date(2024, 1, 1), date(2025, 1, 1), 2, 100.0, 0.01, "BENCH")
    _assert_only_mismatch("return_convention", config=replace(base, return_convention="gross_total_return"))


def test_compatible_pair_has_hand_checked_performance_and_costs() -> None:
    left, right = _backtest_pair()
    result = compare_backtests(left, right)

    # Hand calculation: 110 / 100 - 1 = 10%; 105 / 100 - 1 = 5%.
    # Turnover is 0.20 vs 0.20; costs are $2 vs $1.  Both use the same
    # benchmark return of 5%, so excess returns are 5% and 0%.
    assert result.assumption_mismatches == ()
    assert result.return_a == approx(0.10)
    assert result.return_b == approx(0.05)
    assert result.excess_return_a == approx(0.05)
    assert result.excess_return_b == approx(0.0)
    assert result.turnover_a == approx(0.20)
    assert result.turnover_b == approx(0.20)
    assert result.metadata["performance_a"]["transaction_costs"] == approx(2.0)
    assert result.metadata["performance_b"]["transaction_costs"] == approx(1.0)
    assert result.metadata["comparison_scope"]["return_convention"] == "net_total_return"
