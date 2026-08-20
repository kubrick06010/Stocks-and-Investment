from dataclasses import replace
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
from stocks_investment.storage import SQLiteStorage


NOW = datetime(2026, 2, 15, 12, tzinfo=timezone.utc)


def test_automation_artifacts_round_trip_and_are_immutable(tmp_path) -> None:
    path = tmp_path / "automation.db"
    retry = RetryPolicy(2, 1, 5, (AutomationFailureKind.TRANSIENT,))
    definition = ResearchAutomationDefinition(
        "filing-research", "filing_research_v1", "pipeline_v1",
        (AutomationTriggerKind.FILING_AVAILABLE,), "balanced", "balanced_v1",
        "us-large-cap", None, retry, True, NOW, {"report": True},
    )
    source = SourceReference("filing_document", "filing-1")
    trigger = AutomationTrigger(
        "trigger-1", AutomationTriggerKind.FILING_AVAILABLE, NOW, date(2026, 2, 15),
        "filing:filing-1", (source,), (Ticker("AAA"),),
    )
    output = SourceReference("research_run", "research-1")
    step = AutomationStepResult(
        AutomationStepName.CREATE_RESEARCH_RUN, "research_step_v1",
        AutomationStepStatus.COMPLETED, 1, NOW, NOW, (source,), (output,),
    )
    run = AutomationRun(
        "automation-1", definition.id, definition.version, definition.pipeline_version,
        trigger.id, "filing_research_v1:filing:filing-1", date(2026, 2, 15),
        AutomationRunStatus.COMPLETED, 1, NOW, NOW, NOW, (step,), (source,), (output,),
    )
    with SQLiteStorage(path) as storage:
        storage.save_automation_definition(definition)
        storage.save_automation_trigger(trigger)
        storage.save_automation_run(run)
        with pytest.raises(ValueError, match="immutable automation_runs"):
            storage.save_automation_run(replace(run, status=AutomationRunStatus.FAILED))

    with SQLiteStorage(path) as reopened:
        assert reopened.load_automation_definition(definition.id, definition.version) == definition
        assert reopened.load_automation_trigger(trigger.id) == trigger
        assert reopened.load_automation_run(run.id) == run
        assert reopened.automation_run_for_idempotency_key(run.idempotency_key) == run
        assert reopened.automation_runs(definition.id) == (run,)


def test_definition_versions_remain_distinct(tmp_path) -> None:
    path = tmp_path / "versions.db"
    base = ResearchAutomationDefinition(
        "job", "v1", "pipeline_v1", (AutomationTriggerKind.MANUAL,),
        "strategy", "strategy_v1", "universe", None,
        RetryPolicy(1, 0, 0, ()), True, NOW,
    )
    with SQLiteStorage(path) as storage:
        storage.save_automation_definition(base)
        storage.save_automation_definition(replace(base, version="v2"))
        assert storage.load_automation_definition("job", "v1") == base
        assert storage.load_automation_definition("job", "v2") == replace(base, version="v2")
