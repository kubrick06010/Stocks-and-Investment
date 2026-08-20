from datetime import date, datetime, timezone

import pytest

from stocks_investment.cli import main
from stocks_investment.domain import (
    AutomationRun,
    AutomationRunStatus,
    AutomationTrigger,
    AutomationTriggerKind,
    ResearchAutomationDefinition,
    RetryPolicy,
)
from stocks_investment.storage import SQLiteStorage


NOW = datetime(2026, 2, 15, tzinfo=timezone.utc)


def _persist(path) -> AutomationRun:
    definition = ResearchAutomationDefinition(
        "job", "job_v1", "pipeline_v1", (AutomationTriggerKind.MANUAL,),
        "strategy", "strategy_v1", "universe", None, RetryPolicy(1, 0, 0, ()),
        True, NOW,
    )
    trigger = AutomationTrigger(
        "trigger", AutomationTriggerKind.MANUAL, NOW, date(2026, 2, 15),
        "manual:job:2026-02-15", (),
    )
    run = AutomationRun(
        "automation", definition.id, definition.version, definition.pipeline_version,
        trigger.id, "job_v1:manual:job:2026-02-15", trigger.as_of,
        AutomationRunStatus.COMPLETED, 1, NOW, NOW, NOW,
    )
    with SQLiteStorage(path) as storage:
        storage.save_automation_definition(definition)
        storage.save_automation_trigger(trigger)
        storage.save_automation_run(run)
    return run


@pytest.mark.parametrize("output_format", ("text", "json", "markdown"))
def test_automation_run_cli_reads_persisted_control_plane(
    tmp_path, capsys, output_format
) -> None:
    path = tmp_path / "automation.sqlite"
    _persist(path)
    assert main([
        "automation-run", "automation", "--db", str(path), "--format", output_format,
    ]) == 0
    output = capsys.readouterr().out
    assert "automation" in output.lower()
    assert "pipeline_v1" in output
    assert "Traceback" not in output


def test_automation_run_cli_missing_record_is_clean_error(tmp_path, capsys) -> None:
    path = tmp_path / "empty.sqlite"
    with SQLiteStorage(path):
        pass
    with pytest.raises(SystemExit):
        main(["automation-run", "missing", "--db", str(path)])
    assert "automation run not found" in capsys.readouterr().err
