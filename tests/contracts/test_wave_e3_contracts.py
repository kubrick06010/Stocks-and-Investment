from datetime import date, datetime, timezone

import pytest

from stocks_investment.domain import (
    AutomationFailureKind,
    AutomationRun,
    AutomationRunStatus,
    AutomationStepName,
    AutomationStepResult,
    AutomationStepStatus,
    AutomationTrigger,
    AutomationTriggerKind,
    ResearchAutomationDefinition,
    RetryPolicy,
    SourceReference,
    Ticker,
)


NOW = datetime(2026, 2, 15, 12, tzinfo=timezone.utc)
AS_OF = date(2026, 2, 15)


def _retry() -> RetryPolicy:
    return RetryPolicy(
        3,
        1,
        30,
        (AutomationFailureKind.TRANSIENT, AutomationFailureKind.RATE_LIMITED),
    )


def test_definition_freezes_pipeline_strategy_schedule_and_retry_identity() -> None:
    definition = ResearchAutomationDefinition(
        "quarterly-research",
        "quarterly_research_v1",
        "deterministic_research_pipeline_v1",
        (AutomationTriggerKind.SCHEDULED, AutomationTriggerKind.FILING_AVAILABLE),
        "balanced_value_quality",
        "balanced_value_quality_v1",
        "us-large-cap",
        "0 8 * * 1",
        _retry(),
        True,
        NOW,
    )
    assert definition.strategy_version == "balanced_value_quality_v1"
    assert definition.pipeline_version == "deterministic_research_pipeline_v1"
    with pytest.raises(AttributeError):
        definition.version = "v2"  # type: ignore[misc]


def test_scheduled_definition_requires_explicit_schedule() -> None:
    with pytest.raises(ValueError, match="schedule"):
        ResearchAutomationDefinition(
            "job", "v1", "pipeline_v1", (AutomationTriggerKind.SCHEDULED,),
            "strategy", "strategy_v1", "universe", None, _retry(), True, NOW,
        )


def test_definition_rejects_secret_bearing_parameters() -> None:
    with pytest.raises(ValueError, match="cannot contain secrets"):
        ResearchAutomationDefinition(
            "job", "v1", "pipeline_v1", (AutomationTriggerKind.MANUAL,),
            "strategy", "strategy_v1", "universe", None, _retry(), True, NOW,
            {"api_key": "must-not-persist"},
        )
    with pytest.raises(ValueError, match="cannot contain secrets"):
        ResearchAutomationDefinition(
            "job", "v1", "pipeline_v1", (AutomationTriggerKind.MANUAL,),
            "strategy", "strategy_v1", "universe", None, _retry(), True, NOW,
            {"provider": {"access_token": "must-not-persist"}},
        )


def test_filing_trigger_requires_evidence_and_blocks_future_as_of() -> None:
    reference = SourceReference("filing_document", "filing-1")
    trigger = AutomationTrigger(
        "trigger-1", AutomationTriggerKind.FILING_AVAILABLE, NOW, AS_OF,
        "filing:filing-1", (reference,), (Ticker("AAA"),),
    )
    assert trigger.source_references == (reference,)
    with pytest.raises(ValueError, match="future information"):
        AutomationTrigger(
            "future", AutomationTriggerKind.MANUAL, NOW, date(2026, 2, 16),
            "future", (),
        )


def test_outcome_artifacts_cannot_enter_research_trigger_inputs() -> None:
    with pytest.raises(ValueError, match="future outcome"):
        AutomationTrigger(
            "outcome", AutomationTriggerKind.MANUAL, NOW, AS_OF, "outcome",
            (SourceReference("research_outcome", "future-return"),),
        )


def test_trigger_security_identity_is_sorted_and_deduplicated() -> None:
    with pytest.raises(ValueError, match="unique and sorted"):
        AutomationTrigger(
            "trigger", AutomationTriggerKind.MANUAL, NOW, AS_OF, "key", (),
            (Ticker("BBB"), Ticker("AAA")),
        )


def test_step_result_preserves_input_output_lineage_and_typed_failure() -> None:
    inputs = (SourceReference("filing_document", "filing-1"),)
    outputs = (SourceReference("research_run", "run-1"),)
    completed = AutomationStepResult(
        AutomationStepName.CREATE_RESEARCH_RUN, "research_step_v1",
        AutomationStepStatus.COMPLETED, 1, NOW, NOW, inputs, outputs,
    )
    assert completed.input_references == inputs
    assert completed.output_references == outputs
    with pytest.raises(ValueError, match="typed failure"):
        AutomationStepResult(
            AutomationStepName.BUILD_REPORT, "report_step_v1",
            AutomationStepStatus.FAILED, 1, NOW, NOW, inputs, (),
        )


def test_completed_run_cannot_hide_failed_step() -> None:
    failed = AutomationStepResult(
        AutomationStepName.INGEST_EVIDENCE, "ingest_v1", AutomationStepStatus.FAILED,
        1, NOW, NOW, (), (), AutomationFailureKind.PROVIDER_UNAVAILABLE, "offline", True,
    )
    with pytest.raises(ValueError, match="cannot contain failed"):
        AutomationRun(
            "run", "definition", "definition_v1", "pipeline_v1", "trigger", "idem",
            AS_OF, AutomationRunStatus.COMPLETED, 1, NOW, NOW, NOW, (failed,),
        )


def test_run_preserves_idempotency_versions_and_artifact_lineage() -> None:
    output = SourceReference("research_run", "research-1")
    run = AutomationRun(
        "automation-1", "definition", "definition_v1", "pipeline_v1", "trigger-1",
        "definition_v1:trigger-1", AS_OF, AutomationRunStatus.COMPLETED, 1,
        NOW, NOW, NOW, (), (), (output,),
    )
    assert run.idempotency_key == "definition_v1:trigger-1"
    assert run.output_references == (output,)
