from datetime import date, datetime, timezone

from stocks_investment.automation import (
    DeterministicAutomationOrchestrator,
    FilingTriggerSource,
    StepAdapter,
)
from stocks_investment.domain import (
    AnalysisStatus,
    AutomationFailureKind,
    AutomationRunStatus,
    AutomationStepName,
    AutomationTriggerKind,
    CompositeScore,
    DataProvenance,
    FactorObservation,
    FactorScore,
    FilingDocument,
    FilingEvidenceSnapshot,
    FilingForm,
    MaterialityPolicy,
    MaterialityRule,
    MaterialityRuleType,
    MissingDataPolicy,
    ResearchAutomationDefinition,
    ResearchResult,
    ResearchRun,
    ResearchRunStatus,
    RetryPolicy,
    SourceReference,
    ThesisClassification,
    Ticker,
    UniverseSnapshot,
    WatchCondition,
    WatchlistEntry,
    WatchlistStatus,
)
from stocks_investment.filings.claims import DisclosedRiskPattern, build_disclosed_risk_claims
from stocks_investment.filings.parser import SafeFilingParser
from stocks_investment.history.changes import compare_results
from stocks_investment.reporting import build_automation_run_report, render_automation_run_json
from stocks_investment.reporting.builder import build_historical_stock_report
from stocks_investment.screening.engine import Candidate, ScreeningEngine
from stocks_investment.storage import SQLiteStorage
from stocks_investment.thesis.engine import StructuredThesisEngine
from stocks_investment.watchlist.engine import evaluate_watchlist


UTC = timezone.utc
NOW = datetime(2026, 2, 15, 21, 5, tzinfo=UTC)
AS_OF = NOW.date()
TICKER = Ticker("AAA")
CONTENT = b"""<html><body><h1>Item 1A Risk Factors</h1>
<p>Cybersecurity incidents may disrupt operations.</p></body></html>"""


def _filing(identifier: str, available_at: datetime) -> FilingDocument:
    provenance = DataProvenance(
        "sec:fixture", "fixture", available_at, available_at.date(),
        available_at=available_at, filing_date=available_at.date(),
        period_end=date(2025, 12, 31), raw_identifier=identifier,
    )
    return FilingDocument(
        identifier, TICKER, "0000000001", identifier, FilingForm.FORM_10_K,
        available_at, available_at, date(2025, 12, 31), "annual.htm",
        f"https://example.test/{identifier}", f"sha256:{identifier}",
        available_at, "text/html", len(CONTENT), provenance,
    )


def _factor(score: float, as_of: date, version: str = "quality_v1") -> FactorScore:
    observation = FactorObservation(
        "quality_input", score, AnalysisStatus.VALID, "score", as_of, "annual",
        "quality_input_v1", "quality_input",
    )
    return FactorScore("quality", version, score, AnalysisStatus.VALID, 1, (observation,), "fixture quality")


def _composite(score: float, as_of: date) -> CompositeScore:
    factor = _factor(score, as_of)
    return CompositeScore(
        "balanced_value_quality", "balanced_value_quality_v1", (factor,),
        {"quality": 1}, MissingDataPolicy.INSUFFICIENT_DATA, score,
        AnalysisStatus.VALID, as_of,
    )


def test_filing_trigger_drives_existing_research_services_and_replays_from_storage(tmp_path) -> None:
    path = tmp_path / "wave-e3.db"
    previous_run = ResearchRun(
        "research-prior", datetime(2026, 1, 31, tzinfo=UTC), date(2026, 1, 31),
        "balanced_value_quality", "balanced_value_quality_v1", "fixture", "fixture-v1",
        date(2026, 1, 31), {}, None, "snapshot-prior", ResearchRunStatus.COMPLETED,
    )
    previous_result = ResearchResult(
        "research-prior:AAA", previous_run.id, TICKER, previous_run.created_at,
        1, 65, "selected", (_factor(65, previous_run.as_of),),
    )
    current_filing = _filing("filing-current", NOW)
    future_filing = _filing("filing-future", datetime(2026, 3, 1, tzinfo=UTC))
    definition = ResearchAutomationDefinition(
        "filing-research", "filing_research_v1", "deterministic_pipeline_v1",
        (AutomationTriggerKind.FILING_AVAILABLE,), "balanced_value_quality",
        "balanced_value_quality_v1", "fixture", None,
        RetryPolicy(2, 0, 0, (AutomationFailureKind.TRANSIENT,)), True, NOW,
    )
    entry = WatchlistEntry(
        "watch-aaa", TICKER, previous_run.created_at, previous_run.id, previous_result.id,
        "Revisit when composite quality reaches 80", WatchlistStatus.ACTIVE, 1,
        target_conditions=(WatchCondition("composite_score", ">=", 80, "watch_score_v1"),),
    )

    with SQLiteStorage(path) as storage:
        storage.save_research_run(previous_run)
        storage.save_research_result(previous_result)
        storage.save_thesis_snapshot(StructuredThesisEngine().generate(previous_run, previous_result))
        storage.save_watchlist_entry(entry)
        storage.save_filing_document(current_filing)
        storage.save_filing_document(future_filing)
        storage.save_automation_definition(definition)

        triggers = FilingTriggerSource(storage, (TICKER,)).detect((definition,), NOW)
        assert len(triggers) == 1
        assert triggers[0].source_references == (
            SourceReference("filing_document", current_filing.id),
        )
        assert future_filing.id not in {
            reference.entity_id for reference in triggers[0].source_references
        }
        trigger = triggers[0]
        storage.save_automation_trigger(trigger)

        state: dict[str, object] = {}

        def ingest(_definition, _trigger, _inputs):
            assert storage.load_filing_document(current_filing.id) == current_filing
            return (SourceReference("filing_document", current_filing.id),)

        def normalize(_definition, _trigger, _inputs):
            sections = SafeFilingParser().parse(current_filing, CONTENT)
            for section in sections:
                storage.save_filing_section(section)
            claims = build_disclosed_risk_claims(
                current_filing, sections, as_of=AS_OF,
                patterns=(DisclosedRiskPattern("cybersecurity", "Cybersecurity incidents"),),
                created_at=NOW,
            )
            for claim in claims:
                storage.save_qualitative_claim(claim)
            snapshot = FilingEvidenceSnapshot(
                "filing-snapshot-current", TICKER, AS_OF, (current_filing.id,),
                tuple(section.id for section in sections), tuple(claim.id for claim in claims),
                "filing_snapshot_v1", NOW,
            )
            storage.save_filing_evidence_snapshot(snapshot)
            return (SourceReference("filing_evidence_snapshot", snapshot.id),)

        def research(_definition, _trigger, _inputs):
            screening = ScreeningEngine(storage).run(
                UniverseSnapshot("fixture", "fixture-v2", AS_OF, (TICKER,), "fixture"),
                (Candidate(TICKER, _composite(85, AS_OF)),),
                strategy_name=definition.strategy_name,
                strategy_version=definition.strategy_version,
                run_id="research-current",
                created_at=NOW,
                data_snapshot="filing-snapshot-current",
            )
            state["research_run"] = screening.run.id
            return (
                SourceReference("research_run", screening.run.id),
                SourceReference("research_result", f"{screening.run.id}:AAA"),
            )

        def thesis(_definition, _trigger, _inputs):
            run = storage.load_research_run("research-current")
            result = storage.load_research_result("research-current:AAA")
            assert run is not None and result is not None
            snapshot = StructuredThesisEngine().generate(run, result)
            storage.save_thesis_snapshot(snapshot)
            assert snapshot.classification is ThesisClassification.ATTRACTIVE
            return (SourceReference("thesis_snapshot", snapshot.id),)

        def changes(_definition, _trigger, _inputs):
            run = storage.load_research_run("research-current")
            result = storage.load_research_result("research-current:AAA")
            assert run is not None and result is not None
            policy = MaterialityPolicy(
                "automation_materiality_v1",
                (MaterialityRule("composite_score", MaterialityRuleType.ABSOLUTE, 10, "score_change_v1"),),
            )
            events = compare_results(previous_run, previous_result, run, result, policy)
            for event in events:
                storage.save_change_event(event)
            return tuple(
                SourceReference("research_change_event", f"{event.from_run_id}->{event.to_run_id}:{event.field}")
                for event in events
            )

        def watchlist(_definition, _trigger, _inputs):
            run = storage.load_research_run("research-current")
            result = storage.load_research_result("research-current:AAA")
            assert run is not None and result is not None
            events = evaluate_watchlist(entry, run, result, {"composite_score": 65})
            for event in events:
                storage.save_monitoring_event(event)
            return tuple(
                SourceReference("monitoring_event", f"{event.watchlist_entry_id}:{event.research_run_id}")
                for event in events
            )

        def report(_definition, _trigger, _inputs):
            snapshots = storage.load_thesis_snapshots(TICKER)
            report_value = build_historical_stock_report(
                TICKER.symbol, snapshots, storage.load_change_events(TICKER),
                storage.load_watchlist_entries(), storage.load_monitoring_events(entry.id), (),
            )
            assert report_value.source_run_ids == (previous_run.id, "research-current")
            state["report"] = report_value
            return (SourceReference("research_report", "AAA:2026-02-15"),)

        adapters = {
            AutomationStepName.INGEST_EVIDENCE: StepAdapter("ingest_v1", ingest),
            AutomationStepName.NORMALIZE_OBSERVATIONS: StepAdapter("normalize_v1", normalize),
            AutomationStepName.CREATE_RESEARCH_RUN: StepAdapter("research_v1", research),
            AutomationStepName.GENERATE_THESIS: StepAdapter("thesis_v1", thesis),
            AutomationStepName.DETECT_CHANGES: StepAdapter("changes_v1", changes),
            AutomationStepName.EVALUATE_WATCHLIST: StepAdapter("watchlist_v1", watchlist),
            AutomationStepName.BUILD_REPORT: StepAdapter("report_v1", report),
        }
        automation = DeterministicAutomationOrchestrator(
            adapters,
            read_existing=storage.automation_run_for_idempotency_key,
            write_run=storage.save_automation_run,
            clock=lambda: NOW,
        ).execute(definition, trigger)
        assert automation.status is AutomationRunStatus.COMPLETED
        assert [step.step for step in automation.steps] == list(AutomationStepName)
        assert SourceReference("research_run", "research-current") in automation.output_references

    def provider_kill_switch(*_args, **_kwargs):
        raise AssertionError("persisted automation replay must not call providers or pipeline steps")

    with SQLiteStorage(path) as reopened:
        saved_definition = reopened.load_automation_definition(definition.id, definition.version)
        saved_trigger = reopened.load_automation_trigger(trigger.id)
        saved_run = reopened.load_automation_run(automation.id)
        assert saved_definition == definition
        assert saved_trigger == trigger
        assert saved_run == automation
        assert reopened.load_research_run("research-current") is not None
        assert reopened.load_thesis_snapshots(TICKER)[-1].classification is ThesisClassification.ATTRACTIVE
        assert reopened.load_change_events(TICKER)
        assert reopened.load_monitoring_events(entry.id)[0].triggered is True

        replay_adapters = {
            step: StepAdapter("kill_switch_v1", provider_kill_switch)
            for step in AutomationStepName
        }
        replay = DeterministicAutomationOrchestrator(
            replay_adapters,
            read_existing=reopened.automation_run_for_idempotency_key,
            write_run=provider_kill_switch,
            clock=lambda: NOW,
        ).execute(definition, trigger)
        assert replay == saved_run
        report_value = build_automation_run_report(
            saved_run, definition=saved_definition, trigger=saved_trigger
        )
        rendered = render_automation_run_json(report_value)
        assert '"provider_calls": false' in rendered
        assert "research-current" in rendered
