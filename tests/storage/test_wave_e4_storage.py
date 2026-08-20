from dataclasses import replace
from datetime import date

import pytest

from stocks_investment.domain import (
    ConstraintEvaluation,
    ConstraintStatus,
    ConstructionStatus,
    CurrentPortfolioWeight,
    PortfolioConstraint,
    PortfolioConstraintKind,
    PortfolioConstructionPolicy,
    PortfolioConstructionRequest,
    PortfolioConstructionResult,
    SourceReference,
    TargetPosition,
    Ticker,
    TradeEstimate,
    WeightingMethod,
)
from stocks_investment.storage import SQLiteStorage


def test_portfolio_construction_round_trip_and_immutability(tmp_path) -> None:
    path = tmp_path / "construction.db"
    policy = PortfolioConstructionPolicy(
        "targets", "targets_v1", WeightingMethod.EQUAL_WEIGHT,
        (PortfolioConstraint(PortfolioConstraintKind.MAX_POSITION_WEIGHT, .6, "cap_v1"),),
        "gross_traded_notional", .001, True,
    )
    request = PortfolioConstructionRequest(
        "request", date(2026, 3, 31), "research", ("research:AAA", "research:BBB"),
        policy.name, policy.version, 100_000, "USD",
        (CurrentPortfolioWeight(Ticker("AAA"), .4),),
        (SourceReference("research_run", "research"),),
    )
    targets = (
        TargetPosition(Ticker("AAA"), .5, "research:AAA", 90, "equal"),
        TargetPosition(Ticker("BBB"), .5, "research:BBB", 80, "equal"),
    )
    trades = (
        TradeEstimate(Ticker("AAA"), .4, .5, .1, 10_000, 10),
        TradeEstimate(Ticker("BBB"), 0, .5, .5, 50_000, 50),
    )
    evaluation = ConstraintEvaluation(
        PortfolioConstraintKind.MAX_POSITION_WEIGHT, None, .5, .6,
        ConstraintStatus.SATISFIED, "position cap satisfied",
    )
    result = PortfolioConstructionResult(
        "result", request.id, "constructor_v1", ConstructionStatus.VALID,
        targets, 0, 60_000, .6, 60, trades, (evaluation,),
        (SourceReference("research_run", "research"),),
    )
    with SQLiteStorage(path) as storage:
        storage.save_portfolio_construction_policy(policy)
        storage.save_portfolio_construction_request(request)
        storage.save_portfolio_construction_result(result)
        with pytest.raises(ValueError, match="immutable portfolio_construction_results"):
            storage.save_portfolio_construction_result(replace(result, notes=("rewritten",)))
    with SQLiteStorage(path) as reopened:
        assert reopened.load_portfolio_construction_policy(policy.name, policy.version) == policy
        assert reopened.load_portfolio_construction_request(request.id) == request
        assert reopened.load_portfolio_construction_result(result.id) == result
