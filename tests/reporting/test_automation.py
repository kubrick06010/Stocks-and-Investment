from datetime import date, datetime, timezone
import json

from stocks_investment.domain import (
    AutomationFailureKind,
    AutomationRun,
    AutomationRunStatus,
    AutomationStepName,
    AutomationStepResult,
    AutomationStepStatus,
    AutomationTrigger,
    AutomationTriggerKind,
    RetryPolicy,
    SourceReference,
    Ticker,
)
from stocks_investment.reporting.automation import (
    build_automation_run_report,
    render_automation_run_json,
    render_automation_run_markdown,
    render_automation_run_text,
)


def _times() -> tuple[datetime, datetime]:
    return (
        datetime(2025, 1, 1, 9, tzinfo=timezone.utc),
        datetime(2025, 1, 1, 10, tzinfo=timezone.utc),
    )


def _run(*, status: AutomationRunStatus, steps: tuple[AutomationStepResult, ...]) -> AutomationRun:
    created, finished = _times()
    return AutomationRun(
        "automation-1",
        "daily-research",
        "v1",
        "pipeline-v3",
        "trigger-1",
        "daily-research:2025-01-01",
        date(2025, 1, 1),
        status,
        1,
        created,
        created,
        finished,
        steps,
        (SourceReference("filing", "filing-1"),),
        (SourceReference("research_run", "run-1"),),
    )


def _completed_step() -> AutomationStepResult:
    created, finished = _times()
    return AutomationStepResult(
        AutomationStepName.CREATE_RESEARCH_RUN,
        "step-v1",
        AutomationStepStatus.COMPLETED,
        1,
        created,
        finished,
        (SourceReference("filing", "filing-1"),),
        (SourceReference("research_run", "run-1"),),
    )


def _definition_and_trigger() -> tuple[object, AutomationTrigger]:
    from stocks_investment.domain.automation import ResearchAutomationDefinition

    created, _ = _times()
    definition = ResearchAutomationDefinition(
        "daily-research",
        "v1",
        "pipeline-v3",
        (AutomationTriggerKind.SCHEDULED,),
        "balanced_value_quality",
        "v1",
        "sp500",
        "0 9 * * 1-5",
        RetryPolicy(3, 1.0, 8.0, (AutomationFailureKind.TRANSIENT,)),
        True,
        created,
        {"top_n": 20},
    )
    trigger = AutomationTrigger(
        "trigger-1",
        AutomationTriggerKind.SCHEDULED,
        created,
        date(2025, 1, 1),
        "daily-research:2025-01-01",
        (),
        (Ticker("AAA"),),
    )
    return definition, trigger


def test_completed_report_preserves_definition_trigger_and_lineage() -> None:
    definition, trigger = _definition_and_trigger()
    report = build_automation_run_report(
        _run(status=AutomationRunStatus.COMPLETED, steps=(_completed_step(),)),
        definition=definition,
        trigger=trigger,
    )

    encoded = json.loads(render_automation_run_json(report))
    assert encoded["report_type"] == "automation_run"
    sections = {section["title"]: section for section in encoded["sections"]}
    assert sections["AUTOMATION RUN"]["payload"]["status"] == "completed"
    assert sections["DEFINITION AND TRIGGER"]["payload"]["definition"]["id"] == "daily-research"
    assert sections["DEFINITION AND TRIGGER"]["payload"]["trigger"]["as_of"] == "2025-01-01"
    step = sections["STEP LINEAGE"]["payload"]["steps"][0]
    assert step["input_references"][0]["entity_id"] == "filing-1"
    assert step["output_references"][0]["entity_id"] == "run-1"
    assert encoded["metadata"]["provider_calls"] is False


def test_partial_failure_report_exposes_failures_and_retries() -> None:
    created, finished = _times()
    failed = AutomationStepResult(
        AutomationStepName.GENERATE_THESIS,
        "step-v2",
        AutomationStepStatus.FAILED,
        2,
        created,
        finished,
        (SourceReference("research_run", "run-1"),),
        (),
        AutomationFailureKind.TRANSIENT,
        "temporary unavailable dependency",
        True,
    )
    report = build_automation_run_report(
        _run(status=AutomationRunStatus.PARTIAL_FAILURE, steps=(_completed_step(), failed))
    )
    failures = next(section for section in report.sections if section.title == "FAILURES AND RETRIES")
    assert failures.payload["failure_count"] == 1
    assert failures.payload["retry_count"] == 1
    encoded = render_automation_run_json(report)
    assert "temporary unavailable dependency" in encoded
    assert "transient" in encoded


def test_renderers_are_read_only_and_keep_automation_information_boundary() -> None:
    report = build_automation_run_report(
        _run(status=AutomationRunStatus.COMPLETED, steps=(_completed_step(),))
    )
    text = render_automation_run_text(report)
    markdown = render_automation_run_markdown(report)
    assert "status=completed" in text
    assert "## AUTOMATION RUN" in markdown
    assert "outcome_information_included" not in text
    assert all(section.section_type != "outcome" for section in report.sections)
    assert report.metadata["information_boundary"] == "automation_control_plane"


def test_missing_optional_context_remains_explicit() -> None:
    report = build_automation_run_report(
        _run(status=AutomationRunStatus.FAILED, steps=()),
    )
    definition_section = next(
        section for section in report.sections if section.title == "DEFINITION AND TRIGGER"
    )
    assert definition_section.payload["definition"] == {"available": False}
    assert definition_section.payload["trigger"] == {"available": False}
