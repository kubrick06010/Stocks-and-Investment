from datetime import date
import json

import pytest

from stocks_investment.domain import (
    ConstraintEvaluation,
    ConstraintStatus,
    ConstructionStatus,
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
from stocks_investment.reporting.portfolio_construction import (
    build_portfolio_construction_report,
    render_portfolio_construction_json,
    render_portfolio_construction_markdown,
)


def _objects(status: ConstructionStatus = ConstructionStatus.VALID):
    policy = PortfolioConstructionPolicy(
        "research_targets",
        "research_targets_v1",
        WeightingMethod.EQUAL_WEIGHT,
        (PortfolioConstraint(PortfolioConstraintKind.LONG_ONLY, None, "long_only_v1"),),
        "gross_traded_notional",
        0.001,
        True,
    )
    request = PortfolioConstructionRequest(
        "request-1",
        date(2026, 3, 31),
        "research-1",
        ("research-1:AAA",),
        policy.name,
        policy.version,
        100_000,
        "USD",
        source_references=(SourceReference("research_run", "research-1"),),
    )
    target = TargetPosition(Ticker("AAA"), 0.9, "research-1:AAA", 91, "validated research result")
    constraint = ConstraintEvaluation(
        PortfolioConstraintKind.LONG_ONLY,
        None,
        0,
        None,
        ConstraintStatus.SATISFIED if status is ConstructionStatus.VALID else ConstraintStatus.VIOLATED,
        "long-only policy evaluation",
    )
    result = PortfolioConstructionResult(
        "construction-1",
        request.id,
        policy.version,
        status,
        (target,) if status is ConstructionStatus.VALID else (),
        0.1 if status is ConstructionStatus.VALID else 1,
        12_000,
        0.12,
        12,
        (TradeEstimate(Ticker("AAA"), 0, 0.9, 0.9, 90_000, 90),) if status is ConstructionStatus.VALID else (),
        (constraint,),
        (SourceReference("research_result", "research-1:AAA"),),
        ("no feasible allocation",) if status is ConstructionStatus.INFEASIBLE else (),
    )
    return request, policy, result


def test_valid_report_preserves_targets_constraints_trades_and_lineage() -> None:
    request, policy, result = _objects()
    report = build_portfolio_construction_report(request, policy, result)
    encoded = json.loads(render_portfolio_construction_json(request, policy, result))
    markdown = render_portfolio_construction_markdown(request, policy, result)

    assert report.report_type == "portfolio_construction"
    assert {section.section_type for section in report.sections} == {
        "portfolio_construction",
        "portfolio_targets",
        "portfolio_constraints",
        "portfolio_trades",
        "lineage",
    }
    assert encoded["metadata"]["construction_status"] == "valid"
    assert encoded["sections"][1]["payload"]["cash_weight"] == pytest.approx(0.1)
    assert "gross_traded_notional" in markdown
    assert "research_result:research-1:AAA" in markdown


def test_infeasible_report_keeps_failure_explicit() -> None:
    request, policy, result = _objects(ConstructionStatus.INFEASIBLE)
    encoded = json.loads(render_portfolio_construction_json(request, policy, result))

    assert encoded["metadata"]["construction_status"] == "infeasible"
    constraints = encoded["sections"][2]["payload"]["evaluations"]
    assert constraints[0]["status"] == "violated"
    assert "no feasible allocation" in encoded["sections"][2]["payload"]["notes"]


def test_report_rejects_crossed_request_policy_or_result() -> None:
    request, policy, result = _objects()
    other_request = PortfolioConstructionRequest(
        "request-2", request.as_of, request.research_run_id, request.research_result_ids,
        request.policy_name, request.policy_version, request.capital, request.base_currency,
    )
    with pytest.raises(ValueError, match="does not belong to request"):
        build_portfolio_construction_report(other_request, policy, result)

    other_policy = PortfolioConstructionPolicy(
        policy.name, "research_targets_v2", policy.weighting_method, policy.constraints,
        policy.transaction_cost_model, policy.transaction_cost_rate, policy.allow_fractional_shares,
    )
    with pytest.raises(ValueError, match="does not belong to policy"):
        build_portfolio_construction_report(request, other_policy, result)


def test_constructor_methodology_is_distinct_from_policy_version() -> None:
    request, policy, result = _objects()
    from dataclasses import replace

    report = build_portfolio_construction_report(
        request, policy, replace(result, methodology_version="deterministic_constructor_v1")
    )
    assert report.sections[0].payload["methodology_version"] == "deterministic_constructor_v1"
