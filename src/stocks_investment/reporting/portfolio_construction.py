"""Read-only reporting for portfolio-construction decisions.

This module is deliberately a presentation boundary.  It consumes immutable
construction inputs and results and delegates serialization to the canonical
research-report renderers; it does not construct targets, recalculate costs,
or access providers.
"""

from __future__ import annotations

from stocks_investment.domain.portfolio_construction import (
    PortfolioConstructionPolicy,
    PortfolioConstructionRequest,
    PortfolioConstructionResult,
)
from stocks_investment.domain.research_intelligence import ReportSection, ResearchReport, SourceReference
from stocks_investment.reporting.builder import build_report, render_json, render_markdown


def build_portfolio_construction_report(
    request: PortfolioConstructionRequest,
    policy: PortfolioConstructionPolicy,
    result: PortfolioConstructionResult,
) -> ResearchReport:
    """Build a structured, read-only report from a construction decision.

    The request/result relationship and policy identity are validated here as
    report lineage, but no portfolio arithmetic is performed.  Infeasible
    results are reported with their explicit status, notes, and violated
    constraints instead of being converted into a partial allocation.
    """
    if result.request_id != request.id:
        raise ValueError("construction result does not belong to request")
    if (request.policy_name, request.policy_version) != (policy.name, policy.version):
        raise ValueError("construction request does not belong to policy")
    lineage = _unique_references(
        (
            *request.source_references,
            *result.source_references,
            SourceReference("portfolio_construction_request", request.id),
            SourceReference("portfolio_construction_policy", f"{policy.name}:{policy.version}"),
            SourceReference("portfolio_construction_result", result.id),
            SourceReference("research_run", request.research_run_id),
        )
    )
    sections = (
        ReportSection(
            "CONSTRUCTION SUMMARY",
            "portfolio_construction",
            {
                "status": result.status,
                "as_of": request.as_of,
                "request_id": request.id,
                "research_run_id": request.research_run_id,
                "policy": f"{policy.name}:{policy.version}",
                "methodology_version": result.methodology_version,
                "base_currency": request.base_currency,
                "capital": request.capital,
            },
            lineage,
        ),
        ReportSection(
            "TARGETS AND CASH",
            "portfolio_targets",
            {
                "targets": result.targets,
                "cash_weight": result.cash_weight,
                "allow_fractional_shares": policy.allow_fractional_shares,
                "weighting_method": policy.weighting_method,
            },
            _unique_references(
                (*result.source_references,)
                + tuple(SourceReference("research_result", item.source_result_id) for item in result.targets)
            ),
        ),
        ReportSection(
            "CONSTRAINTS",
            "portfolio_constraints",
            {
                "policy_constraints": policy.constraints,
                "evaluations": result.constraints,
                "notes": result.notes,
            },
            lineage,
        ),
        ReportSection(
            "TRADES AND COSTS",
            "portfolio_trades",
            {
                "trades": result.trades,
                "gross_traded_notional": result.gross_traded_notional,
                "turnover": result.turnover,
                "estimated_transaction_cost": result.estimated_transaction_cost,
                "transaction_cost_model": policy.transaction_cost_model,
                "transaction_cost_rate": policy.transaction_cost_rate,
            },
            lineage,
        ),
        ReportSection(
            "LINEAGE",
            "lineage",
            {
                "request": request,
                "policy": policy,
                "result": result,
                "source_references": lineage,
            },
            lineage,
        ),
    )
    return build_report(
        "portfolio_construction",
        request.as_of,
        (request.research_run_id,),
        sections,
        metadata={
            "construction_status": result.status,
            "information_boundary": "persisted_research_to_construction_report",
        },
    )


def render_portfolio_construction_json(
    request: PortfolioConstructionRequest,
    policy: PortfolioConstructionPolicy,
    result: PortfolioConstructionResult,
) -> str:
    """Render a construction report as canonical JSON."""
    return render_json(build_portfolio_construction_report(request, policy, result))


def render_portfolio_construction_markdown(
    request: PortfolioConstructionRequest,
    policy: PortfolioConstructionPolicy,
    result: PortfolioConstructionResult,
) -> str:
    """Render a construction report as canonical Markdown."""
    return render_markdown(build_portfolio_construction_report(request, policy, result))


def _unique_references(references: tuple[SourceReference, ...]) -> tuple[SourceReference, ...]:
    seen: set[tuple[str, str, str | None]] = set()
    result: list[SourceReference] = []
    for reference in references:
        identity = (reference.entity_type, reference.entity_id, reference.field)
        if identity not in seen:
            seen.add(identity)
            result.append(reference)
    return tuple(result)
