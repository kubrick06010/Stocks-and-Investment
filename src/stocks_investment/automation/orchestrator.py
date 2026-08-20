"""Small deterministic control-plane runner for the frozen E3 contracts.

This module deliberately contains no research calculations, provider access, or
storage implementation.  Existing services are injected as step adapters.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from stocks_investment.domain.automation import (
    AutomationFailureKind,
    AutomationRun,
    AutomationRunStatus,
    AutomationStepName,
    AutomationStepResult,
    AutomationStepStatus,
    AutomationTrigger,
    ResearchAutomationDefinition,
)
from stocks_investment.domain.research_intelligence import SourceReference
from stocks_investment.automation.reliability import canonical_idempotency_key


class AutomationStepFailure(Exception):
    """Typed failure an injected step may raise without hiding its semantics."""

    def __init__(
        self,
        kind: AutomationFailureKind,
        message: str,
        *,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.retryable = kind in {
            AutomationFailureKind.PROVIDER_UNAVAILABLE,
            AutomationFailureKind.RATE_LIMITED,
            AutomationFailureKind.TRANSIENT,
        } if retryable is None else retryable


def _safe_error_message(error: Exception) -> str:
    """Bound and redact an operational message before durable persistence."""

    message = str(error).replace("\n", " ").replace("\r", " ")[:500]
    message = re.sub(r"(?i)(bearer\s+)[^\s,;]+", r"\1[REDACTED]", message)
    message = re.sub(
        r"(?i)((?:api[_-]?key|token|password|secret|authorization|cookie)\s*[=:]\s*)[^\s,;&]+",
        r"\1[REDACTED]",
        message,
    )
    return message


class StepCallable(Protocol):
    def __call__(
        self,
        definition: ResearchAutomationDefinition,
        trigger: AutomationTrigger,
        inputs: tuple[SourceReference, ...],
    ) -> tuple[SourceReference, ...]: ...


@dataclass(frozen=True, slots=True)
class StepAdapter:
    """An injected existing-service callable and its immutable step version."""

    version: str
    call: StepCallable

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("automation step adapter requires a version")


class RunReader(Protocol):
    def __call__(self, idempotency_key: str) -> AutomationRun | None: ...


class RunWriter(Protocol):
    def __call__(self, run: AutomationRun) -> None: ...


_PIPELINE: tuple[AutomationStepName, ...] = (
    AutomationStepName.INGEST_EVIDENCE,
    AutomationStepName.NORMALIZE_OBSERVATIONS,
    AutomationStepName.CREATE_RESEARCH_RUN,
    AutomationStepName.GENERATE_THESIS,
    AutomationStepName.DETECT_CHANGES,
    AutomationStepName.EVALUATE_WATCHLIST,
    AutomationStepName.BUILD_REPORT,
)


def _references_unique(references: tuple[SourceReference, ...]) -> tuple[SourceReference, ...]:
    """Deduplicate references without changing their first-seen order."""

    seen: set[tuple[str, str, str | None]] = set()
    result: list[SourceReference] = []
    for reference in references:
        key = (reference.entity_type, reference.entity_id, reference.field)
        if key not in seen:
            seen.add(key)
            result.append(reference)
    return tuple(result)


def _validate_research_outputs(references: tuple[SourceReference, ...]) -> None:
    outcome_types = {"research_outcome", "outcome_observation", "factor_outcome_observation"}
    if any(reference.entity_type in outcome_types for reference in references):
        raise AutomationStepFailure(
            AutomationFailureKind.INTEGRITY_VIOLATION,
            "automation research step attempted to expose future outcome information",
            retryable=False,
        )


def _identity(
    definition: ResearchAutomationDefinition,
    trigger: AutomationTrigger,
) -> tuple[str, str]:
    idempotency_key = canonical_idempotency_key(definition, trigger.deduplication_key)
    payload = {
        "idempotency_key": idempotency_key,
        "trigger_kind": trigger.kind.value,
        "as_of": trigger.as_of.isoformat(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    return f"automation:{digest}", idempotency_key


class DeterministicAutomationOrchestrator:
    """Execute the seven-step research pipeline exactly once per identity.

    Retry policy is bounded and immediate: retryable step failures are retried
    without sleeping.  A step never receives future data from this class; the
    injected service remains responsible for its existing PIT contract.
    """

    version = "automation_orchestrator_v1"

    def __init__(
        self,
        adapters: Mapping[AutomationStepName, StepAdapter],
        *,
        read_existing: RunReader | None = None,
        write_run: RunWriter | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        missing = tuple(step for step in _PIPELINE if step not in adapters)
        if missing:
            raise ValueError(f"missing automation step adapters: {', '.join(step.value for step in missing)}")
        self._adapters = dict(adapters)
        self._read_existing = read_existing
        self._write_run = write_run
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def execute(
        self,
        definition: ResearchAutomationDefinition,
        trigger: AutomationTrigger,
    ) -> AutomationRun:
        run_id, idempotency_key = _identity(definition, trigger)
        if self._read_existing is not None:
            existing = self._read_existing(idempotency_key)
            if existing is not None:
                return existing

        created_at = self._clock()
        started_at = created_at
        if not definition.enabled or trigger.kind not in definition.trigger_kinds:
            run = self._terminal_run(
                run_id,
                idempotency_key,
                definition,
                trigger,
                created_at,
                started_at,
                AutomationRunStatus.FAILED,
            )
            if self._write_run is not None:
                self._write_run(run)
            return run

        steps: list[AutomationStepResult] = []
        inputs = _references_unique(trigger.source_references)
        outputs: tuple[SourceReference, ...] = ()
        failed = False
        completed_count = 0
        for step in _PIPELINE:
            if failed:
                now = self._clock()
                skipped = AutomationStepResult(
                    step,
                    self._adapters[step].version,
                    AutomationStepStatus.SKIPPED,
                    1,
                    now,
                    now,
                    inputs,
                    (),
                )
                steps.append(skipped)
                continue

            adapter = self._adapters[step]
            result, produced, step_failed = self._execute_step(
                adapter, step, definition, trigger, inputs
            )
            steps.append(result)
            if step_failed:
                failed = True
            else:
                completed_count += 1
                produced = _references_unique(produced)
                outputs = _references_unique(outputs + produced)
                inputs = _references_unique(inputs + produced)

        finished_at = self._clock()
        status = (
            AutomationRunStatus.COMPLETED
            if not failed
            else AutomationRunStatus.PARTIAL_FAILURE
            if completed_count
            else AutomationRunStatus.FAILED
        )
        run = AutomationRun(
            run_id,
            definition.id,
            definition.version,
            definition.pipeline_version,
            trigger.id,
            idempotency_key,
            trigger.as_of,
            status,
            1,
            created_at,
            started_at,
            finished_at,
            tuple(steps),
            trigger.source_references,
            outputs,
        )
        if self._write_run is not None:
            self._write_run(run)
        return run

    def _execute_step(
        self,
        adapter: StepAdapter,
        step: AutomationStepName,
        definition: ResearchAutomationDefinition,
        trigger: AutomationTrigger,
        inputs: tuple[SourceReference, ...],
    ) -> tuple[AutomationStepResult, tuple[SourceReference, ...], bool]:
        max_attempts = definition.retry_policy.max_attempts
        for attempt in range(1, max_attempts + 1):
            started = self._clock()
            try:
                produced = adapter.call(definition, trigger, inputs)
                _validate_research_outputs(produced)
            except AutomationStepFailure as error:
                retry = error.retryable and error.kind in definition.retry_policy.retryable_failures
                if retry and attempt < max_attempts:
                    continue
                finished = self._clock()
                return (
                    AutomationStepResult(
                        step,
                        adapter.version,
                        AutomationStepStatus.FAILED,
                        attempt,
                        started,
                        finished,
                        inputs,
                        (),
                        error.kind,
                        _safe_error_message(error),
                        retry,
                    ),
                    (),
                    True,
                )
            except Exception as error:  # noqa: BLE001 - boundary converts unknown adapter errors
                finished = self._clock()
                return (
                    AutomationStepResult(
                        step,
                        adapter.version,
                        AutomationStepStatus.FAILED,
                        attempt,
                        started,
                        finished,
                        inputs,
                        (),
                        AutomationFailureKind.PERMANENT,
                        f"{type(error).__name__}: adapter failed",
                        False,
                    ),
                    (),
                    True,
                )
            else:
                finished = self._clock()
                return (
                    AutomationStepResult(
                        step,
                        adapter.version,
                        AutomationStepStatus.COMPLETED,
                        attempt,
                        started,
                        finished,
                        inputs,
                        _references_unique(produced),
                    ),
                    tuple(produced),
                    False,
                )
        raise AssertionError("automation retry loop exited without a terminal result")

    def _terminal_run(
        self,
        run_id: str,
        idempotency_key: str,
        definition: ResearchAutomationDefinition,
        trigger: AutomationTrigger,
        created_at: datetime,
        started_at: datetime,
        status: AutomationRunStatus,
    ) -> AutomationRun:
        return AutomationRun(
            run_id,
            definition.id,
            definition.version,
            definition.pipeline_version,
            trigger.id,
            idempotency_key,
            trigger.as_of,
            status,
            1,
            created_at,
            started_at,
            self._clock(),
            (),
            trigger.source_references,
            (),
        )


__all__ = [
    "AutomationStepFailure",
    "DeterministicAutomationOrchestrator",
    "StepAdapter",
]
