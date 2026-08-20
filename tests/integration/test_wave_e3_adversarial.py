"""Independent adversarial tests for Wave E3 research automation.

Ownership fence: this file is intentionally the only production-adjacent
artifact changed by this review.  A failing assertion is evidence of a
production defect; this reviewer does not repair implementation code.
"""

from dataclasses import replace
from datetime import date, datetime, timezone
import sqlite3

import pytest

from stocks_investment.automation import (
    DeterministicAutomationOrchestrator,
    FilingTriggerSource,
    ScheduledTriggerSource,
    StepAdapter,
    build_manual_trigger,
)
from stocks_investment.automation.orchestrator import AutomationStepFailure
from stocks_investment.automation.reliability import canonical_idempotency_key, replay_decision
from stocks_investment.data.providers.sec_filings import SecFilingsProvider
from stocks_investment.domain import (
    AutomationFailureKind,
    AutomationRun,
    AutomationRunStatus,
    AutomationStepName,
    AutomationTrigger,
    AutomationTriggerKind,
    DataProvenance,
    FilingDocument,
    FilingForm,
    ResearchAutomationDefinition,
    RetryPolicy,
    SourceReference,
    Ticker,
)
from stocks_investment.storage import SQLiteStorage


UTC = timezone.utc
NOW = datetime(2026, 8, 19, 8, 0, tzinfo=UTC)


def _definition(
    *,
    version: str = "definition_v1",
    pipeline_version: str = "pipeline_v1",
    strategy_version: str = "strategy_v1",
    retry: RetryPolicy | None = None,
    kinds: tuple[AutomationTriggerKind, ...] = (AutomationTriggerKind.MANUAL,),
    schedule: str | None = None,
) -> ResearchAutomationDefinition:
    return ResearchAutomationDefinition(
        "research-job", version, pipeline_version, kinds, "strategy", strategy_version,
        "fixture", schedule, retry or RetryPolicy(2, 0, 0, (AutomationFailureKind.TRANSIENT,)),
        True, NOW,
    )


def _filing(identifier: str, available_at: datetime) -> FilingDocument:
    provenance = DataProvenance(
        "sec", "fixture", NOW, available_at.date(), available_at=available_at,
        filing_date=available_at.date(), period_end=date(2026, 6, 30),
        raw_identifier=identifier,
    )
    return FilingDocument(
        identifier, Ticker("AAA"), "1", identifier, FilingForm.FORM_10_Q,
        available_at, available_at, date(2026, 6, 30), "quarterly.htm",
        f"https://example.invalid/{identifier}", f"hash-{identifier}",
        max(NOW, available_at),
        "text/plain", 10, provenance,
    )


class _Reader:
    def __init__(self, filings: tuple[FilingDocument, ...]) -> None:
        self.filings = filings

    def load_filings_available_on(self, ticker: Ticker, as_of: date) -> tuple[FilingDocument, ...]:
        return tuple(item for item in self.filings if item.ticker == ticker)


def _trigger(key: str = "delivery-1", *, source: tuple[SourceReference, ...] = ()) -> AutomationTrigger:
    return AutomationTrigger(
        "trigger-" + key, AutomationTriggerKind.MANUAL, NOW, NOW.date(), key, source,
        (Ticker("AAA"),),
    )


def _orchestrator(callbacks=None, **kwargs):
    callbacks = callbacks or {}
    adapters = {
        step: StepAdapter(
            f"{step.value}_v1",
            callbacks.get(step, lambda _definition, _trigger, _inputs: ()),
        )
        for step in AutomationStepName
    }
    return DeterministicAutomationOrchestrator(adapters, clock=lambda: NOW, **kwargs)


def test_filing_future_is_physically_present_but_not_triggered_until_available() -> None:
    old = _filing("old", datetime(2026, 8, 18, 16, tzinfo=UTC))
    future = _filing("future", datetime(2026, 8, 19, 8, 1, tzinfo=UTC))
    source = FilingTriggerSource(_Reader((old, future)), (Ticker("AAA"),))
    definition = _definition(kinds=(AutomationTriggerKind.FILING_AVAILABLE,))

    before = source.detect((definition,), NOW)
    assert tuple(item.source_references[0].entity_id for item in before) == ("old",)
    assert future.id not in {item.source_references[0].entity_id for item in before}

    after = source.detect((definition,), future.available_at)
    assert tuple(item.source_references[0].entity_id for item in after) == ("old", "future")


def test_filing_trigger_identity_is_stable_when_a_later_filing_arrives() -> None:
    old = _filing("old", datetime(2026, 8, 18, 16, tzinfo=UTC))
    new = _filing("new", datetime(2026, 8, 19, 8, 1, tzinfo=UTC))
    definition = _definition(kinds=(AutomationTriggerKind.FILING_AVAILABLE,))
    old_trigger = FilingTriggerSource(_Reader((old,)), (Ticker("AAA"),)).detect((definition,), NOW)[0]
    both = FilingTriggerSource(_Reader((new, old)), (Ticker("AAA"),)).detect(
        (definition,), new.available_at
    )
    assert both[0].id == old_trigger.id
    assert both[0].deduplication_key == old_trigger.deduplication_key
    assert both[1].id != old_trigger.id
    assert both[1].deduplication_key.endswith(":new")


def test_manual_trigger_replay_and_definition_pipeline_strategy_versions_are_distinct() -> None:
    first = build_manual_trigger(_definition(), as_of=NOW.date(), observed_at=NOW)
    replay = build_manual_trigger(_definition(), as_of=NOW.date(), observed_at=NOW)
    changed_definition = build_manual_trigger(
        _definition(version="definition_v2"), as_of=NOW.date(), observed_at=NOW
    )
    assert first == replay
    assert changed_definition != first
    assert first.deduplication_key != changed_definition.deduplication_key
    first_run = _orchestrator().execute(_definition(), _trigger())
    pipeline_run = _orchestrator().execute(
        _definition(pipeline_version="pipeline_v2"), _trigger()
    )
    strategy_run = _orchestrator().execute(
        _definition(strategy_version="strategy_v2"), _trigger()
    )
    assert pipeline_run.id != first_run.id
    assert strategy_run.id != first_run.id


def test_existing_terminal_run_is_reused_and_existing_running_run_is_not_replayed() -> None:
    definition = _definition()
    trigger = _trigger()
    terminal = AutomationRun(
        "run-terminal", "research-job", "definition_v1", "pipeline_v1", trigger.id,
        canonical_idempotency_key(definition, trigger.deduplication_key),
        NOW.date(), AutomationRunStatus.COMPLETED, 1,
        NOW, NOW, NOW,
    )
    running = replace(terminal, id="run-running", status=AutomationRunStatus.RUNNING, finished_at=None)
    assert replay_decision(terminal).value == "reuse_terminal"
    assert replay_decision(running).value == "in_flight"
    calls: list[AutomationStepName] = []
    orchestrator = _orchestrator(
        {step: (lambda _d, _t, _i, step=step: (calls.append(step) or ())) for step in AutomationStepName},
        read_existing=lambda key: terminal if key == terminal.idempotency_key else None,
    )
    result = orchestrator.execute(definition, trigger)
    assert result == terminal
    assert calls == []


def test_retry_budget_and_forbidden_failure_kinds_are_respected() -> None:
    attempts = 0

    def flaky(_definition, _trigger, _inputs):
        nonlocal attempts
        attempts += 1
        raise AutomationStepFailure(AutomationFailureKind.TRANSIENT, "still unavailable")

    run = _orchestrator({AutomationStepName.INGEST_EVIDENCE: flaky}).execute(
        _definition(retry=RetryPolicy(2, 0, 0, (AutomationFailureKind.TRANSIENT,))), _trigger()
    )
    assert attempts == 2
    assert run.steps[0].attempt == 2

    forbidden_attempts = 0

    def forbidden(_definition, _trigger, _inputs):
        nonlocal forbidden_attempts
        forbidden_attempts += 1
        raise AutomationStepFailure(AutomationFailureKind.INTEGRITY_VIOLATION, "tampered")

    forbidden_run = _orchestrator({AutomationStepName.INGEST_EVIDENCE: forbidden}).execute(
        _definition(retry=RetryPolicy(4, 0, 0, (AutomationFailureKind.TRANSIENT,))), _trigger()
    )
    assert forbidden_attempts == 1
    assert forbidden_run.steps[0].failure_kind is AutomationFailureKind.INTEGRITY_VIOLATION


def test_partial_failure_skips_every_downstream_step() -> None:
    calls: list[AutomationStepName] = []

    def fail(_definition, _trigger, _inputs):
        calls.append(AutomationStepName.CREATE_RESEARCH_RUN)
        raise AutomationStepFailure(AutomationFailureKind.PERMANENT, "invalid fixture")

    callbacks = {
        step: (lambda _d, _t, _i, step=step: (calls.append(step) or ()))
        for step in AutomationStepName
    }
    callbacks[AutomationStepName.CREATE_RESEARCH_RUN] = fail
    run = _orchestrator(callbacks).execute(_definition(), _trigger())
    assert run.status is AutomationRunStatus.PARTIAL_FAILURE
    assert calls == [
        AutomationStepName.INGEST_EVIDENCE,
        AutomationStepName.NORMALIZE_OBSERVATIONS,
        AutomationStepName.CREATE_RESEARCH_RUN,
    ]
    assert all(step.status.value == "skipped" for step in run.steps[3:])


def test_sqlite_immutable_automation_conflict_and_reopen(tmp_path) -> None:
    path = tmp_path / "automation.db"
    definition = _definition()
    trigger = _trigger()
    with SQLiteStorage(path) as storage:
        storage.save_automation_definition(definition)
        storage.save_automation_trigger(trigger)
        with pytest.raises(ValueError, match="immutable automation_triggers"):
            storage.save_automation_trigger(replace(trigger, metadata={"tampered": True}))
        with pytest.raises(ValueError, match="immutable automation_triggers"):
            storage.save_automation_trigger(replace(trigger, id="other-id"))
    with SQLiteStorage(path) as reopened:
        assert reopened.load_automation_definition(definition.id, definition.version) == definition
        assert reopened.load_automation_trigger(trigger.id) == trigger


def test_v8_to_v9_migration_preserves_existing_payload(tmp_path) -> None:
    path = tmp_path / "v8.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO schema_meta VALUES ('version', '8')")
        connection.execute(
            "CREATE TABLE raw_payloads (content_hash TEXT PRIMARY KEY, provider TEXT NOT NULL, "
            "endpoint TEXT NOT NULL, parameters_json TEXT NOT NULL, payload TEXT NOT NULL, retrieved_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO raw_payloads VALUES ('sentinel', 'fixture', 'endpoint', '{}', 'payload', '2026-01-01T00:00:00+00:00')"
        )
    with SQLiteStorage(path) as storage:
        assert storage._connection.execute("SELECT value FROM schema_meta WHERE key='version'").fetchone()[0] == "10"
        assert storage._connection.execute("SELECT payload FROM raw_payloads WHERE content_hash='sentinel'").fetchone()[0] == "payload"
        storage._migrate()


def test_trigger_boundary_is_utc_and_cron_minute_exact() -> None:
    definition = _definition(kinds=(AutomationTriggerKind.SCHEDULED,), schedule="0 8 * * 3")
    source = ScheduledTriggerSource()
    assert len(source.detect((definition,), NOW)) == 1
    assert source.detect((definition,), NOW.replace(minute=1)) == ()
    with pytest.raises(ValueError, match="UTC"):
        source.detect((definition,), NOW.replace(tzinfo=None))


def test_reopened_historical_filing_reader_has_provider_kill_switch(tmp_path, monkeypatch) -> None:
    path = tmp_path / "provider-free.db"
    filing = _filing("stored", datetime(2026, 8, 18, 16, tzinfo=UTC))
    definition = _definition(kinds=(AutomationTriggerKind.FILING_AVAILABLE,))
    with SQLiteStorage(path) as storage:
        storage.save_filing_document(filing)
    with SQLiteStorage(path) as reopened:
        def forbidden_provider(*_args, **_kwargs):
            raise AssertionError("provider access after reopen")

        monkeypatch.setattr(SecFilingsProvider, "filings", forbidden_provider)
        source = FilingTriggerSource(reopened, (Ticker("AAA"),))
        # The reopened SQLite reader is the only permitted historical source;
        # no provider object is supplied to the trigger source.
        assert source.detect((definition,), NOW)[0].source_references[0].entity_id == "stored"


def test_outcome_reference_must_not_enter_research_inputs() -> None:
    """Release-blocking boundary: outcomes are post-hoc, never research inputs."""
    outcome = SourceReference("outcome_observation", "future-aaa-12m")
    with pytest.raises(ValueError, match="future outcome"):
        _trigger(source=(outcome,))
