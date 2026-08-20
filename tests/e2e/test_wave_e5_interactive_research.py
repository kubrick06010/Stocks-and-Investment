from datetime import date, datetime, timezone

from stocks_investment.backtesting import BacktestConfigV1, BacktestPeriod, BacktestRun
from stocks_investment.domain import (
    AutomationRun,
    AutomationRunStatus,
    AutomationTrigger,
    AutomationTriggerKind,
    ChangeType,
    ConstraintEvaluation,
    ConstraintStatus,
    ConstructionStatus,
    CurrentPortfolioWeight,
    DataProvenance,
    FactorOutcomeObservation,
    FilingDocument,
    FilingForm,
    MonitoringEvent,
    OutcomeVisibility,
    PortfolioConstraint,
    PortfolioConstraintKind,
    PortfolioConstructionPolicy,
    PortfolioConstructionRequest,
    PortfolioConstructionResult,
    ResearchAutomationDefinition,
    ResearchChangeEvent,
    ResearchOutcome,
    ResearchRun,
    ResearchRunStatus,
    ResearchViewKind,
    ResearchViewRequest,
    ResearchViewStatus,
    RetryPolicy,
    SourceReference,
    TargetPosition,
    ThesisClassification,
    ThesisSnapshot,
    Ticker,
    WatchCondition,
    WatchlistEntry,
    WatchlistStatus,
    WeightingMethod,
)
from stocks_investment.interactive import (
    DeterministicInteractiveResearchService,
    render_research_view,
)
from stocks_investment.storage import ReadOnlySQLiteStorage, SQLiteStorage


UTC = timezone.utc
T0 = date(2024, 3, 31)
T1 = date(2024, 6, 30)
NOW0 = datetime(2024, 3, 31, tzinfo=UTC)
NOW1 = datetime(2024, 6, 30, tzinfo=UTC)


def _populate(path) -> None:
    run0 = ResearchRun(
        "run-t0", NOW0, T0, "balanced", "balanced_v1", "fixture", "fixture-t0",
        T0, {}, status=ResearchRunStatus.COMPLETED,
    )
    run1 = ResearchRun(
        "run-t1", NOW1, T1, "balanced", "balanced_v1", "fixture", "fixture-t1",
        T1, {}, status=ResearchRunStatus.COMPLETED,
    )
    thesis0 = ThesisSnapshot(
        "thesis-t0", Ticker("AAA"), run0.id, "run-t0:AAA", T0,
        "structured_thesis_v1", ThesisClassification.WATCH, "T0 persisted watch",
        created_at=NOW0,
    )
    thesis1 = ThesisSnapshot(
        "thesis-t1", Ticker("AAA"), run1.id, "run-t1:AAA", T1,
        "structured_thesis_v1", ThesisClassification.ATTRACTIVE, "T1 persisted attractive",
        created_at=NOW1,
    )
    change = ResearchChangeEvent(
        Ticker("AAA"), run0.id, run1.id, T0, T1, ChangeType.THESIS_CHANGE,
        "classification", "watch", "attractive", None, "material",
        (SourceReference("thesis_snapshot", thesis0.id), SourceReference("thesis_snapshot", thesis1.id)),
    )
    entry = WatchlistEntry(
        "watch-future", Ticker("AAA"), NOW1, run1.id, "run-t1:AAA",
        "Created at T1", WatchlistStatus.TRIGGERED, 1,
        target_conditions=(WatchCondition("classification", "==", "attractive", "watch_v1"),),
    )
    monitor = MonitoringEvent(
        entry.id, run1.id, T1, entry.target_conditions[0], "watch", "attractive", True,
        "triggered at T1",
    )
    config = BacktestConfigV1(T0, T1, 1, 100_000, .001, "BENCH", universe="fixture")
    period = BacktestPeriod(
        0, run0.id, T0, T0, T1, 100_000, 110_000, .102, .5, 50, .10, .06, .04,
        ("AAA",),
    )
    left = BacktestRun("bt-balanced", "balanced", "balanced_v1", config, (period,), 110_000)
    right = BacktestRun("bt-graham", "graham", "graham_v1", config, (period,), 108_000)
    provenance0 = DataProvenance(
        "sec:old", "fixture", NOW0, T0, available_at=NOW0, filing_date=T0,
        raw_identifier="old",
    )
    provenance1 = DataProvenance(
        "sec:new", "fixture", NOW1, T1, available_at=NOW1, filing_date=T1,
        raw_identifier="new",
    )
    filings = (
        FilingDocument(
            "filing-t0", Ticker("AAA"), "1", "old", FilingForm.FORM_10_Q,
            NOW0, NOW0, T0, "old.htm", "https://example.test/old", "sha256:old",
            NOW0, "text/html", 10, provenance0,
        ),
        FilingDocument(
            "filing-t1", Ticker("AAA"), "1", "new", FilingForm.FORM_10_Q,
            NOW1, NOW1, T1, "new.htm", "https://example.test/new", "sha256:new",
            NOW1, "text/html", 10, provenance1,
        ),
    )
    definition = ResearchAutomationDefinition(
        "job", "job_v1", "pipeline_v1", (AutomationTriggerKind.MANUAL,),
        "balanced", "balanced_v1", "fixture", None, RetryPolicy(1, 0, 0, ()),
        True, NOW0,
    )
    trigger = AutomationTrigger("trigger", AutomationTriggerKind.MANUAL, NOW0, T0, "manual:t0", ())
    automation = AutomationRun(
        "automation-t0", definition.id, definition.version, definition.pipeline_version,
        trigger.id, "job_v1:manual:t0", T0, AutomationRunStatus.COMPLETED, 1,
        NOW0, NOW0, NOW0,
    )
    policy = PortfolioConstructionPolicy(
        "targets", "targets_v1", WeightingMethod.EQUAL_WEIGHT,
        (PortfolioConstraint(PortfolioConstraintKind.LONG_ONLY, None, "long_only_v1"),),
        "gross_traded_notional_v1", 0, True,
    )
    construction_request = PortfolioConstructionRequest(
        "construction-request", T0, run0.id, ("run-t0:AAA",), policy.name,
        policy.version, 100_000, "USD", (CurrentPortfolioWeight(Ticker("AAA"), 1),),
    )
    construction_result = PortfolioConstructionResult(
        "construction-result", construction_request.id, "constructor_v1",
        ConstructionStatus.VALID,
        (TargetPosition(Ticker("AAA"), 1, "run-t0:AAA", 80, "persisted target"),),
        0, 0, 0, 0, (),
        (ConstraintEvaluation(
            PortfolioConstraintKind.LONG_ONLY, None, 1, None,
            ConstraintStatus.SATISFIED, "long only",
        ),),
        (SourceReference("research_run", run0.id),),
    )

    with SQLiteStorage(path) as storage:
        storage.save_research_run(run0)
        storage.save_research_run(run1)
        storage.save_thesis_snapshot(thesis0)
        storage.save_thesis_snapshot(thesis1)
        storage.save_change_event(change)
        storage.save_research_outcome(ResearchOutcome("run-t0:AAA", T1, "3M", 5.0, .06, 4.94))
        storage.save_watchlist_entry(entry)
        storage.save_monitoring_event(monitor)
        storage.save_backtest_run(left)
        storage.save_backtest_run(right)
        for index in range(5):
            storage.save_factor_outcome_observation(FactorOutcomeObservation(
                "quality", "quality_v1", f"factor-run-{index}", Ticker(f"Q{index}"),
                T0, 60 + index * 5, "12M", .02 + index * .02, .01,
                .01 + index * .02, "measured", "fixture", "BENCH", "USD", "quarterly",
            ))
        for filing in filings:
            storage.save_filing_document(filing)
        storage.save_automation_definition(definition)
        storage.save_automation_trigger(trigger)
        storage.save_automation_run(automation)
        storage.save_portfolio_construction_policy(policy)
        storage.save_portfolio_construction_request(construction_request)
        storage.save_portfolio_construction_result(construction_result)


def _request(kind, primary=None, secondary=None, **kwargs) -> ResearchViewRequest:
    return ResearchViewRequest(
        f"query:{kind.value}:{primary or 'all'}:{secondary or ''}", kind,
        "interactive_research_v1", primary, secondary, **kwargs,
    )


def test_read_only_reopen_serves_every_view_without_provider_or_future_state(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "interactive-e2e.db"
    _populate(path)
    before = path.read_bytes()

    def fail_network(*_args, **_kwargs):
        raise AssertionError("interactive historical inspection must not use a provider/network")

    monkeypatch.setattr("socket.create_connection", fail_network)
    with ReadOnlySQLiteStorage(path) as reader:
        service = DeterministicInteractiveResearchService(reader)
        requests = (
            _request(ResearchViewKind.STOCK, "AAA", as_of=T1),
            _request(ResearchViewKind.THESIS_HISTORY, "AAA"),
            _request(ResearchViewKind.CHANGES, "AAA"),
            _request(ResearchViewKind.WATCHLIST),
            _request(ResearchViewKind.FILING, "AAA", as_of=T1),
            _request(ResearchViewKind.FILING_HISTORY, "AAA", as_of=T1),
            _request(ResearchViewKind.BACKTEST, "bt-balanced"),
            _request(ResearchViewKind.STRATEGY_COMPARISON, "bt-balanced", "bt-graham"),
            _request(
                ResearchViewKind.FACTOR_EFFICACY, "quality",
                factor_version="quality_v1", horizon="12M",
            ),
            _request(ResearchViewKind.AUTOMATION_RUN, "automation-t0"),
            _request(ResearchViewKind.PORTFOLIO_CONSTRUCTION, "construction-result"),
        )
        views = tuple(service.query(request) for request in requests)
        assert all(view.status in {
            ResearchViewStatus.VALID, ResearchViewStatus.INSUFFICIENT_DATA,
        } for view in views)
        assert all(view.report is not None for view in views)
        assert tuple(render_research_view(view, "json") for view in views) == tuple(
            render_research_view(service.query(request), "json") for request in requests
        )

        t0 = service.query(_request(ResearchViewKind.STOCK, "AAA", as_of=T0))
        t0_json = render_research_view(t0, "json")
        assert "thesis-t0" in t0_json
        assert "thesis-t1" not in t0_json
        assert "watch-future" not in t0_json
        assert "5.0" not in t0_json

        post_hoc = service.query(_request(
            ResearchViewKind.STOCK, "AAA", as_of=T0,
            outcome_visibility=OutcomeVisibility.SEPARATE,
        ))
        post_hoc_json = render_research_view(post_hoc, "json")
        assert "5.0" in post_hoc_json
        assert '"outcome_sections"' in post_hoc_json
        assert "5.0" not in str(post_hoc.report.sections[0].payload)

    assert path.read_bytes() == before
