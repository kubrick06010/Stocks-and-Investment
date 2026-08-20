"""Lead integration for the frozen Wave E4 portfolio-construction contracts."""

from __future__ import annotations

from typing import Iterable, Mapping, cast

from stocks_investment.domain import (
    ConstructionStatus,
    PortfolioConstructionPolicy,
    PortfolioConstructionRequest,
    PortfolioConstructionResult,
    ResearchResult,
    ResearchRun,
    ResearchRunStatus,
    SourceReference,
    TargetPosition,
    Ticker,
)

from .constraints import apply_constraints
from .trades import reconcile_target_trades
from .weighting import EligibilityMode, WeightingStatus, build_base_weights


class DeterministicPortfolioConstructor:
    """Construct an inspectable target without recalculating research signals.

    V1 treats the result IDs frozen in the request as the complete eligible set.
    Target weights and cash are pre-cost allocation weights.  Transaction costs
    are charged separately on gross traded notional; therefore a non-zero cost
    rate requires enough explicit target cash to fund the estimated cost.
    """

    version = "deterministic_portfolio_constructor_v1"

    def construct(
        self,
        request: PortfolioConstructionRequest,
        policy: PortfolioConstructionPolicy,
        run: ResearchRun,
        results: Iterable[ResearchResult],
    ) -> PortfolioConstructionResult:
        rows = tuple(results)
        references = _source_references(request, rows, policy)
        identity_error = _identity_error(request, policy, run, rows)
        if identity_error is not None:
            return self._failure(
                request, ConstructionStatus.INSUFFICIENT_DATA, references, identity_error
            )

        requested = set(request.research_result_ids)
        selected = tuple(item for item in rows if item.id in requested)
        weighting = build_base_weights(
            selected,
            run_id=run.id,
            method=policy.weighting_method,
            eligibility=EligibilityMode.RANKED,
        )
        if weighting.status is not WeightingStatus.VALID:
            notes = tuple(item.reason for item in weighting.issues)
            return self._failure(
                request,
                ConstructionStatus.INSUFFICIENT_DATA,
                references,
                *notes,
            )

        source_by_ticker = {item.ticker: item for item in weighting.targets}
        current = {item.ticker.symbol: item.weight for item in request.current_weights}
        application = apply_constraints(
            {item.ticker: item.weight for item in weighting.targets},
            policy.constraints,
            current_weights=cast(Mapping[str | Ticker, float], current),
        )
        targets = tuple(
            TargetPosition(
                Ticker(symbol),
                weight,
                source_by_ticker[symbol].result_id,
                source_by_ticker[symbol].score,
                f"{policy.weighting_method.value} target from persisted ResearchResult",
            )
            for symbol, weight in sorted(application.weights.items())
        )
        if not application.feasible:
            return PortfolioConstructionResult(
                _result_id(request), request.id, self.version,
                ConstructionStatus.INFEASIBLE, targets, application.cash_weight,
                0.0, 0.0, 0.0, (), application.evaluations, references,
                application.notes,
            )

        try:
            reconciliation = reconcile_target_trades(
                cast(Mapping[object, float], current),
                cast(Mapping[object, float], application.weights),
                request.capital,
                policy.transaction_cost_rate,
            )
        except ValueError as exc:
            return PortfolioConstructionResult(
                _result_id(request), request.id, self.version,
                ConstructionStatus.INFEASIBLE, targets, application.cash_weight,
                0.0, 0.0, 0.0, (), application.evaluations, references,
                (*application.notes, f"unfunded transaction costs: {exc}"),
            )

        return PortfolioConstructionResult(
            _result_id(request), request.id, self.version, ConstructionStatus.VALID,
            targets, application.cash_weight,
            reconciliation.gross_traded_notional,
            reconciliation.turnover,
            reconciliation.estimated_transaction_cost,
            reconciliation.trades,
            application.evaluations,
            references,
            (*application.notes, "cash allocation is pre-cost; costs are funded from that cash"),
        )

    def _failure(
        self,
        request: PortfolioConstructionRequest,
        status: ConstructionStatus,
        references: tuple[SourceReference, ...],
        *notes: str,
    ) -> PortfolioConstructionResult:
        return PortfolioConstructionResult(
            _result_id(request), request.id, self.version, status, (), 1.0,
            0.0, 0.0, 0.0, (), (), references, tuple(notes),
        )


def _identity_error(
    request: PortfolioConstructionRequest,
    policy: PortfolioConstructionPolicy,
    run: ResearchRun,
    rows: tuple[ResearchResult, ...],
) -> str | None:
    if (request.policy_name, request.policy_version) != (policy.name, policy.version):
        return "request policy identity does not match supplied policy"
    if request.research_run_id != run.id:
        return "request does not reference the supplied ResearchRun"
    if request.as_of != run.as_of:
        return "construction as-of must equal the persisted ResearchRun as-of"
    if run.status is not ResearchRunStatus.COMPLETED:
        return "portfolio construction requires a completed ResearchRun"
    if any(item.run_id != run.id for item in rows):
        return "all supplied ResearchResults must belong to the persisted ResearchRun"
    by_id = {item.id: item for item in rows}
    if len(by_id) != len(rows):
        return "supplied ResearchResult identities must be unique"
    missing = sorted(set(request.research_result_ids) - set(by_id))
    if missing:
        return f"requested ResearchResults are unavailable: {', '.join(missing)}"
    return None


def _source_references(
    request: PortfolioConstructionRequest,
    rows: tuple[ResearchResult, ...],
    policy: PortfolioConstructionPolicy,
) -> tuple[SourceReference, ...]:
    references = [
        *request.source_references,
        SourceReference("portfolio_construction_request", request.id),
        SourceReference("portfolio_construction_policy", f"{policy.name}:{policy.version}"),
        SourceReference("research_run", request.research_run_id),
    ]
    requested = set(request.research_result_ids)
    for item in sorted(rows, key=lambda value: value.id):
        if item.id not in requested:
            continue
        references.append(SourceReference("research_result", item.id))
        references.extend(
            SourceReference("metric_observation", str(observation_id))
            for observation_id in item.source_observation_ids
        )
    seen: set[tuple[str, str, str | None]] = set()
    unique: list[SourceReference] = []
    for reference in references:
        identity = (reference.entity_type, reference.entity_id, reference.field)
        if identity not in seen:
            seen.add(identity)
            unique.append(reference)
    return tuple(unique)


def _result_id(request: PortfolioConstructionRequest) -> str:
    return f"portfolio-construction:{request.id}"
