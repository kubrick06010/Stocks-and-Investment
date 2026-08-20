from datetime import date, datetime, timezone

import pytest

from stocks_investment.automation.orchestrator import (
    AutomationStepFailure,
    DeterministicAutomationOrchestrator,
    StepAdapter,
)
from stocks_investment.domain import (
    AutomationFailureKind,
    AutomationRunStatus,
    AutomationStepName,
    AutomationStepStatus,
    AutomationTrigger,
    AutomationTriggerKind,
    ResearchAutomationDefinition,
    RetryPolicy,
    SourceReference,
    Ticker,
)


NOW = datetime(2026, 8, 19, 12, tzinfo=timezone.utc)


def _definition(*, enabled: bool = True, triggers=(AutomationTriggerKind.MANUAL,), schedule=None):
    return ResearchAutomationDefinition(
        "job", "job_v1", "pipeline_v1", triggers, "strategy", "strategy_v1",
        "universe", schedule, RetryPolicy(2, 0, 0, (AutomationFailureKind.TRANSIENT,)), enabled, NOW,
    )


def _trigger(kind=AutomationTriggerKind.MANUAL, key="delivery-1"):
    return AutomationTrigger(
        "trigger-1", kind, NOW, date(2026, 8, 19), key,
        (SourceReference("filing_document", "filing-1"),) if kind is AutomationTriggerKind.FILING_AVAILABLE else (),
        (Ticker("AAA"),),
    )


def _orchestrator(callbacks=None, **kwargs):
    callbacks = callbacks or {}
    adapters = {
        step: StepAdapter(f"{step.value}_v1", callbacks.get(
            step, lambda _definition, _trigger, _inputs, step=step: (
                SourceReference(step.value, f"{step.value}-1"),
            )
        ))
        for step in AutomationStepName
    }
    return DeterministicAutomationOrchestrator(adapters, clock=lambda: NOW, **kwargs)


def test_executes_exact_order_and_chains_artifact_lineage() -> None:
    calls = []
    callbacks = {}
    for step in AutomationStepName:
        def callback(_definition, _trigger, inputs, step=step):
            calls.append((step, inputs))
            return (SourceReference("artifact", step.value),)
        callbacks[step] = callback

    run = _orchestrator(callbacks).execute(_definition(), _trigger())

    assert run.status is AutomationRunStatus.COMPLETED
    assert [step for step, _ in calls] == list(AutomationStepName)
    assert run.output_references == tuple(SourceReference("artifact", step.value) for step in AutomationStepName)
    assert calls[0][1] == ()
    assert calls[1][1] == (SourceReference("artifact", AutomationStepName.INGEST_EVIDENCE.value),)
    assert all(result.status is AutomationStepStatus.COMPLETED for result in run.steps)


def test_idempotency_returns_existing_run_without_reinvoking_steps() -> None:
    executions = []
    orchestrator = _orchestrator({step: (lambda d, t, i, step=step: (executions.append(step) or ()))
                                  for step in AutomationStepName})
    # The reader is installed after constructing the first result to model a durable store.
    first = orchestrator.execute(_definition(), _trigger())
    def reader(key):
        return first if key == first.idempotency_key else None

    second = _orchestrator(read_existing=reader).execute(_definition(), _trigger())
    assert second is first
    assert executions == list(AutomationStepName)


def test_retryable_failure_is_bounded_without_sleep_and_records_attempt() -> None:
    attempts = 0

    def flaky(_definition, _trigger, _inputs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise AutomationStepFailure(AutomationFailureKind.TRANSIENT, "temporary")
        return (SourceReference("research_run", "run-1"),)

    callbacks = {AutomationStepName.INGEST_EVIDENCE: flaky}
    run = _orchestrator(callbacks).execute(_definition(), _trigger())
    assert run.status is AutomationRunStatus.COMPLETED
    assert attempts == 2
    assert run.steps[0].attempt == 2


def test_failure_is_partial_and_remaining_steps_are_skipped() -> None:
    def fail(_definition, _trigger, _inputs):
        raise AutomationStepFailure(AutomationFailureKind.PERMANENT, "bad artifact")

    run = _orchestrator({AutomationStepName.CREATE_RESEARCH_RUN: fail}).execute(_definition(), _trigger())
    assert run.status is AutomationRunStatus.PARTIAL_FAILURE
    assert run.steps[2].status is AutomationStepStatus.FAILED
    assert all(step.status is AutomationStepStatus.SKIPPED for step in run.steps[3:])
    assert run.steps[2].failure_kind is AutomationFailureKind.PERMANENT


def test_disabled_or_incompatible_definition_is_terminal_and_does_not_run_steps() -> None:
    calls = []
    callbacks = {step: (lambda d, t, i, step=step: (calls.append(step) or ())) for step in AutomationStepName}
    run = _orchestrator(callbacks).execute(_definition(enabled=False), _trigger())
    assert run.status is AutomationRunStatus.FAILED
    assert run.steps == ()
    assert calls == []

    run = _orchestrator(callbacks).execute(
        _definition(triggers=(AutomationTriggerKind.SCHEDULED,), schedule="0 8 * * 1"), _trigger()
    )
    assert run.status is AutomationRunStatus.FAILED
    assert calls == []


def test_filing_trigger_source_is_run_lineage() -> None:
    run = _orchestrator().execute(
        _definition(triggers=(AutomationTriggerKind.FILING_AVAILABLE,)),
        _trigger(AutomationTriggerKind.FILING_AVAILABLE),
    )
    assert run.source_references == (SourceReference("filing_document", "filing-1"),)
    assert run.steps[0].input_references == run.source_references


def test_identities_are_stable_and_change_with_definition_or_trigger_delivery() -> None:
    first = _orchestrator().execute(_definition(), _trigger())
    same = _orchestrator().execute(_definition(), _trigger())
    changed = _orchestrator().execute(_definition(), _trigger(key="delivery-2"))
    assert first.id == same.id
    assert first.idempotency_key == same.idempotency_key
    assert changed.id != first.id


def test_missing_adapter_is_rejected_before_execution() -> None:
    adapters = {step: StepAdapter("v1", lambda d, t, i: ()) for step in AutomationStepName}
    adapters.pop(AutomationStepName.BUILD_REPORT)
    with pytest.raises(ValueError, match="missing automation step"):
        DeterministicAutomationOrchestrator(adapters)


def test_failure_messages_are_bounded_and_secret_values_are_redacted() -> None:
    def fail(_definition, _trigger, _inputs):
        raise AutomationStepFailure(
            AutomationFailureKind.PERMANENT,
            "provider failed api_key=super-secret Bearer abc.def password=hunter2",
        )

    run = _orchestrator({AutomationStepName.INGEST_EVIDENCE: fail}).execute(
        _definition(), _trigger()
    )
    message = run.steps[0].error_message or ""
    assert "super-secret" not in message
    assert "abc.def" not in message
    assert "hunter2" not in message
    assert "[REDACTED]" in message


def test_future_outcome_output_is_blocked_as_integrity_violation() -> None:
    def leak(_definition, _trigger, _inputs):
        return (SourceReference("research_outcome", "future-12m"),)

    run = _orchestrator({AutomationStepName.INGEST_EVIDENCE: leak}).execute(
        _definition(), _trigger()
    )
    assert run.status is AutomationRunStatus.FAILED
    assert run.steps[0].failure_kind is AutomationFailureKind.INTEGRITY_VIOLATION
