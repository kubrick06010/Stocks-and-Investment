"""Independent adversarial review of the Wave E4 construction flow.

These tests intentionally exercise the public contracts from the outside.  They
do not patch production behavior and do not use live data.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from stocks_investment.domain import (
    ConstructionStatus,
    CurrentPortfolioWeight,
    PortfolioConstraint,
    PortfolioConstraintKind,
    PortfolioConstructionPolicy,
    PortfolioConstructionRequest,
    ResearchResult,
    ResearchRun,
    ResearchRunStatus,
    Ticker,
    WeightingMethod,
)
from stocks_investment.portfolio_construction import DeterministicPortfolioConstructor
from stocks_investment.portfolio_construction.constraints import apply_constraints
from stocks_investment.portfolio_construction.trades import reconcile_target_trades
from stocks_investment.storage import SQLiteStorage


AS_OF = date(2026, 3, 31)
CREATED_AT = datetime(2026, 3, 31, tzinfo=timezone.utc)


def _run(run_id: str = "e4f-run", as_of: date = AS_OF) -> ResearchRun:
    return ResearchRun(
        run_id,
        CREATED_AT,
        as_of,
        "balanced_value_quality",
        "balanced_value_quality_v1",
        "e4f_fixture",
        "e4f_fixture_v1",
        as_of,
        {},
        None,
        "e4f-snapshot",
        ResearchRunStatus.COMPLETED,
    )


def _results(run_id: str = "e4f-run") -> tuple[ResearchResult, ...]:
    return tuple(
        ResearchResult(
            f"{run_id}:{symbol}",
            run_id,
            Ticker(symbol),
            CREATED_AT,
            rank,
            score,
            "selected",
        )
        for rank, (symbol, score) in enumerate(
            (("AAA", 90.0), ("BBB", 80.0), ("CCC", 70.0)),
            start=1,
        )
    )


def _policy(*constraints: PortfolioConstraint, rate: float = 0.0) -> PortfolioConstructionPolicy:
    return PortfolioConstructionPolicy(
        "e4f_policy",
        "e4f_policy_v1",
        WeightingMethod.EQUAL_WEIGHT,
        constraints,
        "gross_traded_notional_v1",
        rate,
        True,
    )


def _request(
    run: ResearchRun,
    policy: PortfolioConstructionPolicy,
    result_ids: tuple[str, ...] | None = None,
    current: tuple[CurrentPortfolioWeight, ...] = (),
) -> PortfolioConstructionRequest:
    return PortfolioConstructionRequest(
        "e4f-request",
        run.as_of,
        run.id,
        result_ids or tuple(item.id for item in _results(run.id)),
        policy.name,
        policy.version,
        100_000.0,
        "USD",
        current,
    )


def test_middle_ticker_removal_cannot_shift_trade_identity() -> None:
    result = reconcile_target_trades(
        {"AAA": 0.2, "BBB": 0.3, "CCC": 0.5},
        {"AAA": 0.4, "CCC": 0.6},
        1_000.0,
        0.0,
    )
    trades = {trade.ticker.symbol: trade for trade in result.trades}

    assert trades["AAA"].traded_notional == pytest.approx(200.0)
    assert trades["BBB"].traded_notional == pytest.approx(300.0)
    assert trades["CCC"].traded_notional == pytest.approx(100.0)


def test_input_order_replay_is_deterministic_and_identity_keyed() -> None:
    run = _run()
    policy = _policy(PortfolioConstraint(PortfolioConstraintKind.MIN_CASH_WEIGHT, 0.02, "cash_v1"))
    request = _request(run, policy, current=(CurrentPortfolioWeight(Ticker("AAA"), 0.4),))
    rows = _results()
    constructor = DeterministicPortfolioConstructor()

    forward = constructor.construct(request, policy, run, rows)
    reverse = constructor.construct(request, policy, run, tuple(reversed(rows)))

    assert forward == reverse
    assert tuple(item.ticker.symbol for item in forward.targets) == ("AAA", "BBB", "CCC")
    assert tuple(item.ticker.symbol for item in forward.trades) == ("AAA", "BBB", "CCC")


def test_zero_turnover_has_zero_cost_and_partial_turnover_is_exact() -> None:
    unchanged = reconcile_target_trades(
        {"AAA": 0.5, "BBB": 0.5}, {"BBB": 0.5, "AAA": 0.5}, 100_000.0, 0.01
    )
    assert unchanged.turnover == pytest.approx(0.0)
    assert unchanged.estimated_transaction_cost == pytest.approx(0.0)

    partial = reconcile_target_trades(
        {"AAA": 0.5, "BBB": 0.4}, {"AAA": 0.5, "CCC": 0.4}, 100_000.0, 0.01
    )
    assert partial.gross_traded_notional == pytest.approx(80_000.0)
    assert partial.turnover == pytest.approx(0.8)
    assert partial.estimated_transaction_cost == pytest.approx(800.0)
    assert partial.cash_after == pytest.approx(9_200.0)


def test_fully_invested_nonzero_cost_fails_without_leverage() -> None:
    # The target consumes all pre-trade capital; the 1% cost cannot be funded.
    # A ValueError is the required honest failure, not a negative cash balance.
    with pytest.raises(ValueError, match="negative cash"):
        reconcile_target_trades({"AAA": 1.0}, {"BBB": 1.0}, 100_000.0, 0.01)

    run = _run()
    policy = _policy(
        PortfolioConstraint(PortfolioConstraintKind.LONG_ONLY, None, "long_only_v1"),
        rate=0.01,
    )
    request = _request(run, policy, result_ids=("e4f-run:AAA", "e4f-run:BBB"))
    constructed = DeterministicPortfolioConstructor().construct(request, policy, run, _results())
    assert constructed.status is ConstructionStatus.INFEASIBLE
    assert any("unfunded transaction costs" in note for note in constructed.notes)
    assert constructed.trades == ()


def test_cash_reserve_funds_costs_without_creating_money() -> None:
    run = _run()
    policy = _policy(
        PortfolioConstraint(PortfolioConstraintKind.MIN_CASH_WEIGHT, 0.10, "cash_v1"),
        rate=0.01,
    )
    request = _request(run, policy, current=(CurrentPortfolioWeight(Ticker("AAA"), 0.5),))
    result = DeterministicPortfolioConstructor().construct(request, policy, run, _results())

    assert result.status is ConstructionStatus.VALID
    assert result.cash_weight == pytest.approx(0.10)
    assert result.estimated_transaction_cost == pytest.approx(800.0)
    # The persisted target remains pre-cost; the residual cash must cover cost.
    assert 100_000.0 * result.cash_weight >= result.estimated_transaction_cost


def test_constraints_report_infeasible_and_missing_sector_explicitly() -> None:
    sector_cap = PortfolioConstraint(
        PortfolioConstraintKind.MAX_SECTOR_WEIGHT, 0.4, "sector_v1", "Technology"
    )
    missing = apply_constraints(
        {"AAA": 0.6, "BBB": 0.4},
        (sector_cap,),
        sector_map={"AAA": "Technology"},
    )
    assert not missing.feasible
    assert any(item.status.value == "not_evaluated" for item in missing.evaluations)

    impossible = apply_constraints(
        {"AAA": 0.7, "BBB": 0.3},
        (sector_cap,),
        sector_map={"AAA": "Technology", "BBB": "Technology"},
    )
    assert not impossible.feasible


def test_request_run_asof_and_result_identity_mismatches_are_rejected() -> None:
    run = _run()
    policy = _policy()
    constructor = DeterministicPortfolioConstructor()
    request = _request(run, policy)

    wrong_run = _run("other-run")
    result = constructor.construct(request, policy, wrong_run, _results())
    assert result.status is ConstructionStatus.INSUFFICIENT_DATA
    assert "request does not reference" in result.notes[0]

    later = _run(as_of=date(2026, 4, 1))
    result = constructor.construct(request, policy, later, _results())
    assert result.status is ConstructionStatus.INSUFFICIENT_DATA
    assert "as-of" in result.notes[0]

    foreign_rows = _results("foreign-run")
    result = constructor.construct(request, policy, run, foreign_rows)
    assert result.status is ConstructionStatus.INSUFFICIENT_DATA
    assert "belong" in result.notes[0]


def test_persistence_round_trip_preserves_research_lineage(tmp_path) -> None:
    run = _run()
    rows = _results()
    policy = _policy(PortfolioConstraint(PortfolioConstraintKind.MIN_CASH_WEIGHT, 0.1, "cash_v1"))
    request = _request(run, policy, current=(CurrentPortfolioWeight(Ticker("AAA"), 0.5),))
    result = DeterministicPortfolioConstructor().construct(request, policy, run, rows)
    assert result.status is ConstructionStatus.VALID

    path = tmp_path / "e4f.db"
    with SQLiteStorage(path) as storage:
        storage.save_research_run(run)
        for row in rows:
            storage.save_research_result(row)
        storage.save_portfolio_construction_policy(policy)
        storage.save_portfolio_construction_request(request)
        storage.save_portfolio_construction_result(result)

    with SQLiteStorage(path) as reopened:
        loaded = reopened.load_portfolio_construction_result(result.id)
        assert loaded == result
        assert {ref.entity_id for ref in loaded.source_references} >= {
            run.id,
            *(row.id for row in rows),
        }
        assert reopened.load_research_run(run.id) == run
        assert reopened.load_research_results(run.id) == rows


def test_constructor_has_no_provider_or_network_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_network(*_: object, **__: object) -> None:
        raise AssertionError("network access is forbidden in portfolio construction")

    monkeypatch.setattr("socket.create_connection", fail_network)
    run = _run()
    policy = _policy()
    request = _request(run, policy)
    result = DeterministicPortfolioConstructor().construct(request, policy, run, _results())

    assert result.status is ConstructionStatus.VALID
