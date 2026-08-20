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
    SourceReference,
    Ticker,
    WeightingMethod,
)
from stocks_investment.portfolio_construction import DeterministicPortfolioConstructor
from stocks_investment.reporting import (
    build_portfolio_construction_report,
    render_portfolio_construction_json,
    render_portfolio_construction_markdown,
)
from stocks_investment.storage import SQLiteStorage


def test_persisted_research_drives_reproducible_funded_target_after_reopen(tmp_path) -> None:
    as_of = date(2026, 3, 31)
    created_at = datetime(2026, 3, 31, tzinfo=timezone.utc)
    run = ResearchRun(
        "e4-research", created_at, as_of, "balanced_value_quality",
        "balanced_value_quality_v1", "historical_fixture", "fixture@2026-03-31",
        as_of, {}, None, "snapshot-e4", ResearchRunStatus.COMPLETED,
    )
    results = (
        ResearchResult("e4-research:AAA", run.id, Ticker("AAA"), created_at, 1, 90, "selected"),
        ResearchResult("e4-research:BBB", run.id, Ticker("BBB"), created_at, 2, 80, "selected"),
    )
    policy = PortfolioConstructionPolicy(
        "research_targets", "research_targets_v1", WeightingMethod.SCORE_PROPORTIONAL,
        (
            PortfolioConstraint(PortfolioConstraintKind.LONG_ONLY, None, "long_only_v1"),
            PortfolioConstraint(PortfolioConstraintKind.MAX_POSITION_WEIGHT, .6, "position_cap_v1"),
            PortfolioConstraint(PortfolioConstraintKind.MIN_CASH_WEIGHT, .02, "cash_reserve_v1"),
        ),
        "gross_traded_notional_v1", .001, True,
    )
    request = PortfolioConstructionRequest(
        "e4-request", as_of, run.id, tuple(item.id for item in results),
        policy.name, policy.version, 100_000, "USD",
        (CurrentPortfolioWeight(Ticker("AAA"), .5), CurrentPortfolioWeight(Ticker("CCC"), .3)),
        (SourceReference("research_run", run.id),),
    )
    path = tmp_path / "wave-e4.db"
    with SQLiteStorage(path) as storage:
        storage.save_research_run(run)
        for item in results:
            storage.save_research_result(item)
        loaded_run = storage.load_research_run(run.id)
        loaded_results = storage.load_research_results(run.id)
        assert loaded_run is not None
        result = DeterministicPortfolioConstructor().construct(
            request, policy, loaded_run, loaded_results
        )
        assert result.status is ConstructionStatus.VALID
        storage.save_portfolio_construction_policy(policy)
        storage.save_portfolio_construction_request(request)
        storage.save_portfolio_construction_result(result)

    with SQLiteStorage(path) as reopened:
        persisted_policy = reopened.load_portfolio_construction_policy(policy.name, policy.version)
        persisted_request = reopened.load_portfolio_construction_request(request.id)
        persisted_result = reopened.load_portfolio_construction_result(result.id)
        assert persisted_policy == policy
        assert persisted_request == request
        assert persisted_result == result
        assert reopened.load_research_results(run.id) == results

        repeated = DeterministicPortfolioConstructor().construct(
            request, policy, run, tuple(reversed(results))
        )
        assert repeated == result
        assert persisted_result.cash_weight == pytest.approx(.02)
        assert persisted_result.estimated_transaction_cost > 0
        report = build_portfolio_construction_report(request, policy, persisted_result)
        assert report.source_run_ids == (run.id,)
        assert '"information_boundary": "persisted_research_to_construction_report"' in render_portfolio_construction_json(request, policy, persisted_result)
        assert "TRADES AND COSTS" in render_portfolio_construction_markdown(request, policy, persisted_result)
