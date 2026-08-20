from datetime import date, datetime, timezone

import pytest

from stocks_investment.automation.reliability import (
    ReplayDecision,
    assert_valid_run_transition,
    canonical_idempotency_key,
    replay_decision,
    retry_decision,
    retry_delay_seconds,
    valid_run_transition,
)
from stocks_investment.domain.automation import (
    AutomationFailureKind,
    AutomationRun,
    AutomationRunStatus,
    AutomationTriggerKind,
    ResearchAutomationDefinition,
    RetryPolicy,
)


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _policy(
    *,
    max_attempts: int = 4,
    retryable: tuple[AutomationFailureKind, ...] = (
        AutomationFailureKind.TRANSIENT,
        AutomationFailureKind.PROVIDER_UNAVAILABLE,
    ),
) -> RetryPolicy:
    return RetryPolicy(max_attempts, 2.0, 5.0, retryable)


def _definition(version: str = "definition_v1") -> ResearchAutomationDefinition:
    return ResearchAutomationDefinition(
        id="daily-research",
        version=version,
        pipeline_version="pipeline_v1",
        trigger_kinds=(AutomationTriggerKind.MANUAL,),
        strategy_name="balanced_value_quality",
        strategy_version="balanced_value_quality_v1",
        universe_name="fixture",
        schedule=None,
        retry_policy=_policy(),
        enabled=True,
        created_at=NOW,
    )


def _run(status: AutomationRunStatus) -> AutomationRun:
    started = NOW if status is not AutomationRunStatus.CREATED else None
    finished = NOW if status in {
        AutomationRunStatus.COMPLETED,
        AutomationRunStatus.PARTIAL_FAILURE,
        AutomationRunStatus.FAILED,
        AutomationRunStatus.CANCELLED,
    } else None
    return AutomationRun(
        id=f"run-{status}",
        definition_id="daily-research",
        definition_version="definition_v1",
        pipeline_version="pipeline_v1",
        trigger_id="trigger-1",
        idempotency_key="definition_v1:trigger-1",
        as_of=date(2026, 1, 1),
        status=status,
        attempt=1,
        created_at=NOW,
        started_at=started,
        finished_at=finished,
    )


def test_idempotency_key_uses_definition_version_and_trigger_key() -> None:
    first = canonical_idempotency_key(_definition(), "filing:abc")
    assert first.startswith("automation-key:")
    assert first == canonical_idempotency_key(_definition(), "filing:abc")
    assert first != canonical_idempotency_key(_definition("definition_v2"), "filing:abc")
    assert first != canonical_idempotency_key(_definition(), "filing:def")
    with pytest.raises(ValueError):
        canonical_idempotency_key(_definition(), " ")


def test_run_transition_table_is_explicit_and_terminal_states_are_immutable() -> None:
    assert valid_run_transition(AutomationRunStatus.CREATED, AutomationRunStatus.RUNNING)
    assert valid_run_transition(AutomationRunStatus.RUNNING, AutomationRunStatus.COMPLETED)
    assert valid_run_transition(AutomationRunStatus.CREATED, AutomationRunStatus.CANCELLED)
    assert not valid_run_transition(AutomationRunStatus.COMPLETED, AutomationRunStatus.RUNNING)
    assert not valid_run_transition(AutomationRunStatus.RUNNING, AutomationRunStatus.CREATED)
    with pytest.raises(ValueError, match="invalid automation run transition"):
        assert_valid_run_transition(AutomationRunStatus.FAILED, AutomationRunStatus.RUNNING)


def test_retry_uses_policy_and_attempt_budget() -> None:
    decision = retry_decision(_policy(), AutomationFailureKind.TRANSIENT, 1)
    assert decision.eligible is True
    assert decision.delay_seconds == 2.0
    assert retry_decision(_policy(), AutomationFailureKind.TRANSIENT, 4).eligible is False
    assert retry_decision(_policy(), AutomationFailureKind.PERMANENT, 1).eligible is False
    assert retry_decision(_policy(), AutomationFailureKind.INVALID_INPUT, 1).eligible is False
    assert retry_decision(_policy(), AutomationFailureKind.INTEGRITY_VIOLATION, 1).eligible is False


def test_policy_can_explicitly_opt_in_to_other_failure_kinds() -> None:
    policy = _policy(
        retryable=(AutomationFailureKind.PERMANENT, AutomationFailureKind.INTEGRITY_VIOLATION)
    )
    assert retry_decision(policy, AutomationFailureKind.PERMANENT, 1).eligible is True
    assert retry_decision(policy, AutomationFailureKind.INTEGRITY_VIOLATION, 1).eligible is True


def test_backoff_is_deterministic_and_capped_without_sleep_or_jitter() -> None:
    policy = _policy()
    assert [retry_delay_seconds(policy, n) for n in (1, 2, 3, 4, 5)] == [2.0, 4.0, 5.0, 5.0, 5.0]
    with pytest.raises(ValueError):
        retry_delay_seconds(policy, 0)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (None, ReplayDecision.START_NEW),
        (AutomationRunStatus.CREATED, ReplayDecision.RESUME_CREATED),
        (AutomationRunStatus.RUNNING, ReplayDecision.IN_FLIGHT),
        (AutomationRunStatus.COMPLETED, ReplayDecision.REUSE_TERMINAL),
        (AutomationRunStatus.PARTIAL_FAILURE, ReplayDecision.REUSE_TERMINAL),
        (AutomationRunStatus.FAILED, ReplayDecision.REUSE_TERMINAL),
        (AutomationRunStatus.CANCELLED, ReplayDecision.REUSE_TERMINAL),
    ],
)
def test_replay_decision_is_based_on_existing_run_state(
    status: AutomationRunStatus | None,
    expected: ReplayDecision,
) -> None:
    assert replay_decision(None if status is None else _run(status)) is expected
