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


def _policy() -> PortfolioConstructionPolicy:
    return PortfolioConstructionPolicy(
        "research_targets", "research_targets_v1", WeightingMethod.EQUAL_WEIGHT,
        (
            PortfolioConstraint(PortfolioConstraintKind.LONG_ONLY, None, "long_only_v1"),
            PortfolioConstraint(PortfolioConstraintKind.MAX_POSITION_WEIGHT, .6, "max_position_v1"),
        ),
        "gross_traded_notional", .001, True,
    )


def test_policy_freezes_weighting_constraints_and_cost_semantics() -> None:
    policy = _policy()
    assert policy.weighting_method is WeightingMethod.EQUAL_WEIGHT
    assert policy.transaction_cost_model == "gross_traded_notional"
    with pytest.raises(AttributeError):
        policy.version = "v2"  # type: ignore[misc]


def test_sector_constraint_requires_scope_and_bounded_limit() -> None:
    with pytest.raises(ValueError, match="sector scope"):
        PortfolioConstraint(PortfolioConstraintKind.MAX_SECTOR_WEIGHT, .3, "sector_v1")
    with pytest.raises(ValueError, match="0..1"):
        PortfolioConstraint(PortfolioConstraintKind.MAX_TURNOVER, 1.2, "turnover_v1")


def test_request_preserves_exact_research_identity_and_current_weights() -> None:
    request = PortfolioConstructionRequest(
        "request-1", date(2026, 3, 31), "research-1", ("research-1:AAA", "research-1:BBB"),
        _policy().name, _policy().version, 100_000, "USD",
        (CurrentPortfolioWeight(Ticker("AAA"), .4), CurrentPortfolioWeight(Ticker("BBB"), .5)),
        (SourceReference("research_run", "research-1"),),
    )
    assert request.research_run_id == "research-1"
    with pytest.raises(ValueError, match="ticker-sorted"):
        PortfolioConstructionRequest(
            "bad", request.as_of, request.research_run_id, request.research_result_ids,
            request.policy_name, request.policy_version, request.capital, request.base_currency,
            tuple(reversed(request.current_weights)), request.source_references,
        )


def test_trade_estimate_reconciles_weight_delta_and_money() -> None:
    trade = TradeEstimate(Ticker("AAA"), .2, .5, .3, 30_000, 30)
    assert trade.target_weight - trade.current_weight == pytest.approx(trade.weight_delta)
    with pytest.raises(ValueError, match="does not reconcile"):
        TradeEstimate(Ticker("AAA"), .2, .5, .1, 30_000, 30)


def test_valid_result_is_decomposable_and_must_reconcile_weights() -> None:
    target = TargetPosition(Ticker("AAA"), .9, "research-1:AAA", 90, "equal target")
    constraint = ConstraintEvaluation(
        PortfolioConstraintKind.LONG_ONLY, None, 0, None, ConstraintStatus.SATISFIED,
        "all targets are non-negative",
    )
    result = PortfolioConstructionResult(
        "construction-1", "request-1", "constructor_v1", ConstructionStatus.VALID,
        (target,), .1, 100_000, 1, 100, (), (constraint,),
        (SourceReference("research_result", "research-1:AAA"),),
    )
    assert result.targets == (target,)
    with pytest.raises(ValueError, match="sum to one"):
        PortfolioConstructionResult(
            "bad", "request-1", "constructor_v1", ConstructionStatus.VALID,
            (target,), 0, 0, 0, 0, (), (constraint,), (),
        )


def test_infeasible_result_keeps_constraint_failure_explicit() -> None:
    failure = ConstraintEvaluation(
        PortfolioConstraintKind.MAX_POSITION_WEIGHT, None, .8, .5,
        ConstraintStatus.VIOLATED, "single eligible security exceeds cap",
    )
    result = PortfolioConstructionResult(
        "infeasible", "request", "constructor_v1", ConstructionStatus.INFEASIBLE,
        (), 1, 0, 0, 0, (), (failure,), (), ("no feasible allocation",),
    )
    assert result.status is ConstructionStatus.INFEASIBLE


def test_non_finite_money_and_weights_are_rejected() -> None:
    with pytest.raises(ValueError, match="positive capital"):
        PortfolioConstructionRequest(
            "request", date(2026, 3, 31), "run", ("run:AAA",), "policy", "v1",
            float("nan"), "USD",
        )
    with pytest.raises(ValueError, match="finite"):
        TradeEstimate(Ticker("AAA"), 0, 1, 1, float("inf"), 0)
