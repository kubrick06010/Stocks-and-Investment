"""Pure reliability decisions for the research-automation control plane.

This module deliberately contains no persistence, sleeping, scheduling, or
orchestration.  It turns frozen automation contracts into deterministic
idempotency, transition, retry, and replay decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json

from stocks_investment.domain.automation import (
    AutomationFailureKind,
    AutomationRun,
    AutomationRunStatus,
    ResearchAutomationDefinition,
    RetryPolicy,
)


class ReplayDecision(StrEnum):
    """What an executor should do when a run with the same key exists."""

    START_NEW = "start_new"
    RESUME_CREATED = "resume_created"
    IN_FLIGHT = "in_flight"
    REUSE_TERMINAL = "reuse_terminal"


@dataclass(frozen=True, slots=True)
class RetryDecision:
    """A retry decision with its deterministic delay, when eligible."""

    eligible: bool
    delay_seconds: float
    reason: str


_TERMINAL_STATUSES = frozenset(
    {
        AutomationRunStatus.COMPLETED,
        AutomationRunStatus.PARTIAL_FAILURE,
        AutomationRunStatus.FAILED,
        AutomationRunStatus.CANCELLED,
    }
)


def canonical_idempotency_key(
    definition: ResearchAutomationDefinition,
    trigger_key: str,
) -> str:
    """Return the stable key for one definition version and trigger.

    The definition *version* is intentional: changing a definition creates a
    new execution identity even when the trigger is the same.  Whitespace is
    rejected rather than normalized, because silently changing an upstream
    trigger key would weaken replay diagnostics.
    """

    if not trigger_key or not trigger_key.strip():
        raise ValueError("trigger key is required for idempotency")
    payload = {
        "definition_id": definition.id,
        "definition_version": definition.version,
        "pipeline_version": definition.pipeline_version,
        "strategy_name": definition.strategy_name,
        "strategy_version": definition.strategy_version,
        "universe_name": definition.universe_name,
        "parameters": definition.parameters,
        "trigger_key": trigger_key,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"automation-key:{hashlib.sha256(canonical.encode()).hexdigest()}"


def valid_run_transition(
    current: AutomationRunStatus,
    target: AutomationRunStatus,
) -> bool:
    """Return whether a run may move directly from ``current`` to ``target``."""

    transitions = {
        AutomationRunStatus.CREATED: frozenset(
            {AutomationRunStatus.RUNNING, AutomationRunStatus.CANCELLED}
        ),
        AutomationRunStatus.RUNNING: frozenset(
            {
                AutomationRunStatus.COMPLETED,
                AutomationRunStatus.PARTIAL_FAILURE,
                AutomationRunStatus.FAILED,
                AutomationRunStatus.CANCELLED,
            }
        ),
    }
    return target in transitions.get(current, frozenset())


def assert_valid_run_transition(
    current: AutomationRunStatus,
    target: AutomationRunStatus,
) -> None:
    """Raise a clear error when a requested status transition is invalid."""

    if not valid_run_transition(current, target):
        raise ValueError(f"invalid automation run transition: {current} -> {target}")


def retry_delay_seconds(policy: RetryPolicy, failed_attempt: int) -> float:
    """Calculate capped exponential backoff for a failed attempt.

    ``failed_attempt=1`` yields the initial backoff.  The function performs no
    waiting and uses no random jitter, making retry plans reproducible.
    """

    if failed_attempt < 1:
        raise ValueError("failed attempt must be positive")
    delay: float = policy.initial_backoff_seconds * (2 ** (failed_attempt - 1))
    return delay if delay < policy.maximum_backoff_seconds else policy.maximum_backoff_seconds


def retry_decision(
    policy: RetryPolicy,
    failure_kind: AutomationFailureKind,
    failed_attempt: int,
) -> RetryDecision:
    """Determine whether a typed failure may be retried.

    Policy membership is the explicit opt-in for every failure kind,
    including invalid input, integrity violations, and permanent failures.
    The attempt budget is checked independently of failure classification.
    """

    if failed_attempt < 1:
        raise ValueError("failed attempt must be positive")
    if failed_attempt >= policy.max_attempts:
        return RetryDecision(False, 0.0, "maximum attempts exhausted")
    if failure_kind not in policy.retryable_failures:
        return RetryDecision(False, 0.0, f"failure kind is not retryable: {failure_kind}")
    return RetryDecision(
        True,
        retry_delay_seconds(policy, failed_attempt),
        f"retryable failure: {failure_kind}",
    )


def replay_decision(existing_run: AutomationRun | None) -> ReplayDecision:
    """Decide whether a duplicate execution may start.

    A missing run is new, a created run can be claimed, a running run is
    treated as in flight, and every terminal run is reused as the immutable
    result for that idempotency key.
    """

    if existing_run is None:
        return ReplayDecision.START_NEW
    if existing_run.status is AutomationRunStatus.CREATED:
        return ReplayDecision.RESUME_CREATED
    if existing_run.status is AutomationRunStatus.RUNNING:
        return ReplayDecision.IN_FLIGHT
    if existing_run.status in _TERMINAL_STATUSES:
        return ReplayDecision.REUSE_TERMINAL
    raise ValueError(f"unsupported automation run status: {existing_run.status}")
