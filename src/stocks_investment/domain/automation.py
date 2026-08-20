"""Versioned, auditable contracts for deterministic research automation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Mapping

from .models import Ticker
from .research_intelligence import SourceReference


def _validate_parameter_value(value: object, path: str = "parameters") -> None:
    sensitive_fragments = ("api_key", "token", "password", "secret", "authorization", "cookie")
    if value is None or isinstance(value, (bool, int, float, str)):
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("automation parameter keys must be strings")
            if any(fragment in key.lower() for fragment in sensitive_fragments):
                raise ValueError("automation parameters cannot contain secrets")
            _validate_parameter_value(item, f"{path}.{key}")
        return
    if isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            _validate_parameter_value(item, f"{path}[{index}]")
        return
    raise ValueError(f"automation parameter is not a JSON value: {path}")


class AutomationTriggerKind(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    FILING_AVAILABLE = "filing_available"


class AutomationStepName(StrEnum):
    INGEST_EVIDENCE = "ingest_evidence"
    NORMALIZE_OBSERVATIONS = "normalize_observations"
    CREATE_RESEARCH_RUN = "create_research_run"
    GENERATE_THESIS = "generate_thesis"
    DETECT_CHANGES = "detect_changes"
    EVALUATE_WATCHLIST = "evaluate_watchlist"
    BUILD_REPORT = "build_report"


class AutomationStepStatus(StrEnum):
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class AutomationRunStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AutomationFailureKind(StrEnum):
    INVALID_INPUT = "invalid_input"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    RATE_LIMITED = "rate_limited"
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    INTEGRITY_VIOLATION = "integrity_violation"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int
    initial_backoff_seconds: float
    maximum_backoff_seconds: float
    retryable_failures: tuple[AutomationFailureKind, ...]

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("retry policy requires at least one attempt")
        if self.initial_backoff_seconds < 0:
            raise ValueError("retry backoff cannot be negative")
        if self.maximum_backoff_seconds < self.initial_backoff_seconds:
            raise ValueError("maximum backoff cannot be smaller than initial backoff")
        if len(self.retryable_failures) != len(set(self.retryable_failures)):
            raise ValueError("retryable failure kinds must be unique")


@dataclass(frozen=True, slots=True)
class ResearchAutomationDefinition:
    id: str
    version: str
    pipeline_version: str
    trigger_kinds: tuple[AutomationTriggerKind, ...]
    strategy_name: str
    strategy_version: str
    universe_name: str
    schedule: str | None
    retry_policy: RetryPolicy
    enabled: bool
    created_at: datetime
    parameters: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        required = (
            self.id,
            self.version,
            self.pipeline_version,
            self.strategy_name,
            self.strategy_version,
            self.universe_name,
        )
        if not all(value.strip() for value in required):
            raise ValueError("automation identity, pipeline, strategy and universe are required")
        if not self.trigger_kinds or len(self.trigger_kinds) != len(set(self.trigger_kinds)):
            raise ValueError("automation trigger kinds must be non-empty and unique")
        if AutomationTriggerKind.SCHEDULED in self.trigger_kinds and not self.schedule:
            raise ValueError("scheduled automation requires an explicit schedule")
        _validate_parameter_value(self.parameters)


@dataclass(frozen=True, slots=True)
class AutomationTrigger:
    id: str
    kind: AutomationTriggerKind
    occurred_at: datetime
    as_of: date
    deduplication_key: str
    source_references: tuple[SourceReference, ...]
    tickers: tuple[Ticker, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.deduplication_key.strip():
            raise ValueError("trigger identity and deduplication key are required")
        symbols = tuple(ticker.symbol for ticker in self.tickers)
        if symbols != tuple(sorted(set(symbols))):
            raise ValueError("trigger tickers must be unique and sorted")
        if self.kind is AutomationTriggerKind.FILING_AVAILABLE and not self.source_references:
            raise ValueError("filing triggers require a filing source reference")
        outcome_types = {"research_outcome", "outcome_observation", "factor_outcome_observation"}
        if any(reference.entity_type in outcome_types for reference in self.source_references):
            raise ValueError("future outcome artifacts cannot trigger historical research")
        if self.occurred_at.date() < self.as_of:
            raise ValueError("trigger cannot make future information available")


@dataclass(frozen=True, slots=True)
class AutomationStepResult:
    step: AutomationStepName
    step_version: str
    status: AutomationStepStatus
    attempt: int
    started_at: datetime
    finished_at: datetime
    input_references: tuple[SourceReference, ...]
    output_references: tuple[SourceReference, ...]
    failure_kind: AutomationFailureKind | None = None
    error_message: str | None = None
    retryable: bool = False

    def __post_init__(self) -> None:
        if not self.step_version.strip() or self.attempt < 1:
            raise ValueError("step version and positive attempt are required")
        if self.finished_at < self.started_at:
            raise ValueError("automation step cannot finish before it starts")
        if self.status is AutomationStepStatus.FAILED:
            if self.failure_kind is None or not self.error_message:
                raise ValueError("failed steps require a typed failure and message")
        elif self.failure_kind is not None or self.error_message is not None or self.retryable:
            raise ValueError("successful/skipped steps cannot carry failure state")


@dataclass(frozen=True, slots=True)
class AutomationRun:
    id: str
    definition_id: str
    definition_version: str
    pipeline_version: str
    trigger_id: str
    idempotency_key: str
    as_of: date
    status: AutomationRunStatus
    attempt: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    steps: tuple[AutomationStepResult, ...] = ()
    source_references: tuple[SourceReference, ...] = ()
    output_references: tuple[SourceReference, ...] = ()

    def __post_init__(self) -> None:
        required = (
            self.id,
            self.definition_id,
            self.definition_version,
            self.pipeline_version,
            self.trigger_id,
            self.idempotency_key,
        )
        if not all(value.strip() for value in required) or self.attempt < 1:
            raise ValueError("automation run identity, versions and attempt are required")
        if self.started_at is not None and self.started_at < self.created_at:
            raise ValueError("automation run cannot start before creation")
        if self.finished_at is not None and self.started_at is None:
            raise ValueError("finished automation run requires a start time")
        if (
            self.finished_at is not None
            and self.started_at is not None
            and self.finished_at < self.started_at
        ):
            raise ValueError("automation run cannot finish before it starts")
        terminal = {
            AutomationRunStatus.COMPLETED,
            AutomationRunStatus.PARTIAL_FAILURE,
            AutomationRunStatus.FAILED,
            AutomationRunStatus.CANCELLED,
        }
        if self.status in terminal and self.finished_at is None:
            raise ValueError("terminal automation run requires a finish time")
        if self.status is AutomationRunStatus.COMPLETED and any(
            step.status is AutomationStepStatus.FAILED for step in self.steps
        ):
            raise ValueError("completed automation run cannot contain failed steps")
