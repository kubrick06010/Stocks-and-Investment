"""Read-only reports for deterministic research-automation runs.

This module is deliberately an edge adapter.  It consumes already persisted
automation artifacts and assembles a :class:`ResearchReport`; it does not
execute a pipeline, resolve providers, or fetch missing definition/trigger
data.  Optional definition and trigger objects are supplied by the caller
when that context has already been loaded from the authoritative store.
"""

from __future__ import annotations

from stocks_investment.domain.automation import (
    AutomationRun,
    AutomationStepResult,
    AutomationTrigger,
    ResearchAutomationDefinition,
)
from stocks_investment.domain.research_intelligence import (
    ReportSection,
    ResearchReport,
    SourceReference,
)
from stocks_investment.reporting.builder import build_report, render_json, render_markdown


def _reference_payload(reference: SourceReference) -> dict[str, str]:
    payload = {"entity_type": reference.entity_type, "entity_id": reference.entity_id}
    if reference.field is not None:
        payload["field"] = reference.field
    return payload


def _references_payload(references: tuple[SourceReference, ...]) -> tuple[dict[str, str], ...]:
    return tuple(_reference_payload(reference) for reference in references)


def _definition_payload(definition: ResearchAutomationDefinition | None) -> dict[str, object]:
    if definition is None:
        return {"available": False}
    return {
        "available": True,
        "id": definition.id,
        "version": definition.version,
        "pipeline_version": definition.pipeline_version,
        "trigger_kinds": tuple(kind.value for kind in definition.trigger_kinds),
        "strategy_name": definition.strategy_name,
        "strategy_version": definition.strategy_version,
        "universe_name": definition.universe_name,
        "schedule": definition.schedule,
        "retry_policy": {
            "max_attempts": definition.retry_policy.max_attempts,
            "initial_backoff_seconds": definition.retry_policy.initial_backoff_seconds,
            "maximum_backoff_seconds": definition.retry_policy.maximum_backoff_seconds,
            "retryable_failures": tuple(
                failure.value for failure in definition.retry_policy.retryable_failures
            ),
        },
        "enabled": definition.enabled,
        "parameters": dict(definition.parameters),
    }


def _trigger_payload(trigger: AutomationTrigger | None) -> dict[str, object]:
    if trigger is None:
        return {"available": False}
    return {
        "available": True,
        "id": trigger.id,
        "kind": trigger.kind.value,
        "occurred_at": trigger.occurred_at,
        "as_of": trigger.as_of,
        "deduplication_key": trigger.deduplication_key,
        "tickers": tuple(ticker.symbol for ticker in trigger.tickers),
        "metadata": dict(trigger.metadata),
        "source_references": _references_payload(trigger.source_references),
    }


def _step_payload(step: AutomationStepResult) -> dict[str, object]:
    payload: dict[str, object] = {
        "step": step.step.value,
        "step_version": step.step_version,
        "status": step.status.value,
        "attempt": step.attempt,
        "started_at": step.started_at,
        "finished_at": step.finished_at,
        "input_references": _references_payload(step.input_references),
        "output_references": _references_payload(step.output_references),
    }
    if step.failure_kind is not None:
        payload["failure_kind"] = step.failure_kind.value
    if step.error_message is not None:
        payload["error_message"] = step.error_message
    if step.retryable:
        payload["retryable"] = True
    return payload


def build_automation_run_report(
    run: AutomationRun,
    *,
    definition: ResearchAutomationDefinition | None = None,
    trigger: AutomationTrigger | None = None,
) -> ResearchReport:
    """Build a deterministic, read-only report for one automation run.

    ``definition`` and ``trigger`` are optional because an ``AutomationRun``
    remains reportable after a caller has loaded only the run record.  The
    report always exposes the immutable IDs stored on the run; when the
    optional records are present it additionally exposes their frozen fields.
    No lookup or recomputation occurs here.
    """

    steps = tuple(_step_payload(step) for step in run.steps)
    failures = tuple(step for step in steps if step["status"] == "failed")
    retries = tuple(_step_payload(step) for step in run.steps if step.attempt > 1)
    source_references = run.source_references + run.output_references
    run_reference = SourceReference("automation_run", run.id)

    overview = {
        "automation_run_id": run.id,
        "definition_id": run.definition_id,
        "definition_version": run.definition_version,
        "pipeline_version": run.pipeline_version,
        "trigger_id": run.trigger_id,
        "idempotency_key": run.idempotency_key,
        "as_of": run.as_of,
        "status": run.status.value,
        "attempt": run.attempt,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
    }
    definition_section = {
        "definition": _definition_payload(definition),
        "trigger": _trigger_payload(trigger),
    }

    sections = (
        ReportSection("AUTOMATION RUN", "automation", overview, (run_reference,)),
        ReportSection(
            "DEFINITION AND TRIGGER",
            "automation",
            definition_section,
            tuple(
                reference
                for reference in (
                    SourceReference("automation_definition", run.definition_id),
                    SourceReference("automation_trigger", run.trigger_id),
                )
                if reference.entity_id
            ),
        ),
        ReportSection(
            "STEP LINEAGE",
            "automation",
            {"steps": steps},
            run.source_references + run.output_references,
        ),
        ReportSection(
            "FAILURES AND RETRIES",
            "automation",
            {
                "failed_steps": failures,
                "retried_steps": retries,
                "failure_count": len(failures),
                "retry_count": len(retries),
            },
            (run_reference,),
        ),
    )
    return build_report(
        "automation_run",
        run.as_of,
        (run.id,),
        sections,
        metadata={
            "automation_run_id": run.id,
            "information_boundary": "automation_control_plane",
            "outcome_information_included": False,
            "provider_calls": False,
            "source_references": _references_payload(source_references),
        },
    )


def render_automation_run_json(report: ResearchReport) -> str:
    """Render an automation report with the shared JSON renderer."""

    return render_json(report)


def render_automation_run_markdown(report: ResearchReport) -> str:
    """Render an automation report with the shared Markdown renderer."""

    return render_markdown(report)


def render_automation_run_text(report: ResearchReport) -> str:
    """Render a compact text view without changing the canonical report."""

    lines = [f"Automation run {report.metadata['automation_run_id']}"]
    for section in report.sections:
        lines.append(section.title)
        if section.section_type != "automation":
            continue
        if section.title == "AUTOMATION RUN":
            payload = section.payload
            lines.append(
                f"status={payload['status']} as_of={payload['as_of']} "
                f"pipeline={payload['pipeline_version']}"
            )
        elif section.title == "FAILURES AND RETRIES":
            lines.append(
                f"failures={section.payload['failure_count']} "
                f"retries={section.payload['retry_count']}"
            )
    return "\n".join(lines)


__all__ = [
    "build_automation_run_report",
    "render_automation_run_json",
    "render_automation_run_markdown",
    "render_automation_run_text",
]
