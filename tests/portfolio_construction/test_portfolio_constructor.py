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


AS_OF = date(2026, 3, 31)
NOW = datetime(2026, 3, 31, tzinfo=timezone.utc)


def _run() -> ResearchRun:
    return ResearchRun(
        "run-1", NOW, AS_OF, "balanced", "balanced_v1", "fixture",
        "fixture@2026-03-31", AS_OF, {}, None, "snapshot-1",
        ResearchRunStatus.COMPLETED,
    )


def _result(symbol: str, rank: int, score: float) -> ResearchResult:
    return ResearchResult(
        f"run-1:{symbol}", "run-1", Ticker(symbol), NOW, rank, score, "selected",
        source_observation_ids=(rank,),
    )


def _policy(*, cash: float | None = .02) -> PortfolioConstructionPolicy:
    constraints = [
        PortfolioConstraint(PortfolioConstraintKind.LONG_ONLY, None, "long_only_v1"),
        PortfolioConstraint(PortfolioConstraintKind.MAX_POSITION_WEIGHT, .6, "position_cap_v1"),
    ]
    if cash is not None:
        constraints.append(
            PortfolioConstraint(PortfolioConstraintKind.MIN_CASH_WEIGHT, cash, "cash_reserve_v1")
        )
    return PortfolioConstructionPolicy(
        "research_targets", "research_targets_v1", WeightingMethod.EQUAL_WEIGHT,
        tuple(constraints), "gross_traded_notional_v1", .001, True,
    )


def _request(policy: PortfolioConstructionPolicy) -> PortfolioConstructionRequest:
    return PortfolioConstructionRequest(
        "request-1", AS_OF, "run-1", ("run-1:AAA", "run-1:CCC"),
        policy.name, policy.version, 100_000, "USD",
        (
            CurrentPortfolioWeight(Ticker("AAA"), .4),
            CurrentPortfolioWeight(Ticker("BBB"), .4),
        ),
    )


def test_constructor_is_identity_safe_constraint_and_cost_aware() -> None:
    policy = _policy()
    result = DeterministicPortfolioConstructor().construct(
        _request(policy), policy, _run(),
        (_result("CCC", 2, 80), _result("AAA", 1, 90), _result("BBB", 3, 70)),
    )

    assert result.status is ConstructionStatus.VALID
    assert [(item.ticker.symbol, item.target_weight) for item in result.targets] == [
        ("AAA", pytest.approx(.49)), ("CCC", pytest.approx(.49)),
    ]
    assert result.cash_weight == pytest.approx(.02)
    assert [(item.ticker.symbol, item.traded_notional) for item in result.trades] == [
        ("AAA", pytest.approx(9_000)),
        ("BBB", pytest.approx(40_000)),
        ("CCC", pytest.approx(49_000)),
    ]
    assert result.gross_traded_notional == pytest.approx(98_000)
    assert result.turnover == pytest.approx(.98)
    assert result.estimated_transaction_cost == pytest.approx(98)
    assert {ref.entity_id for ref in result.source_references} >= {
        "run-1", "run-1:AAA", "run-1:CCC", "1", "2",
    }


def test_constructor_refuses_to_create_leverage_when_costs_are_unfunded() -> None:
    policy = _policy(cash=None)
    result = DeterministicPortfolioConstructor().construct(
        _request(policy), policy, _run(), (_result("AAA", 1, 90), _result("CCC", 2, 80)),
    )

    assert result.status is ConstructionStatus.INFEASIBLE
    assert any("unfunded transaction costs" in note for note in result.notes)
    assert result.trades == ()


def test_constructor_rejects_missing_or_future_mismatched_research_identity() -> None:
    policy = _policy()
    request = _request(policy)
    missing = DeterministicPortfolioConstructor().construct(
        request, policy, _run(), (_result("AAA", 1, 90),)
    )
    assert missing.status is ConstructionStatus.INSUFFICIENT_DATA
    assert "run-1:CCC" in missing.notes[0]

    later = ResearchRun(
        "run-1", NOW, date(2026, 4, 1), "balanced", "balanced_v1", "fixture",
        "fixture@2026-04-01", date(2026, 4, 1), {}, None, "later",
        ResearchRunStatus.COMPLETED,
    )
    mismatch = DeterministicPortfolioConstructor().construct(
        request, policy, later, (_result("AAA", 1, 90), _result("CCC", 2, 80))
    )
    assert mismatch.status is ConstructionStatus.INSUFFICIENT_DATA
    assert "as-of" in mismatch.notes[0]
