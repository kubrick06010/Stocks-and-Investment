"""Provider-independent seams for the research-automation control plane."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Protocol

from stocks_investment.domain.automation import (
    AutomationRun,
    AutomationTrigger,
    ResearchAutomationDefinition,
)


class ResearchAutomationOrchestrator(Protocol):
    """Coordinate the existing deterministic pipeline and return artifact lineage."""

    version: str

    def execute(
        self,
        definition: ResearchAutomationDefinition,
        trigger: AutomationTrigger,
    ) -> AutomationRun: ...


class AutomationTriggerSource(Protocol):
    """Produce dated triggers; it does not execute research or mutate evidence."""

    name: str

    def detect(
        self,
        definitions: Iterable[ResearchAutomationDefinition],
        observed_at: datetime,
    ) -> tuple[AutomationTrigger, ...]: ...


class AutomationRunReader(Protocol):
    """Read durable run state for idempotency and historical inspection."""

    def automation_run_for_idempotency_key(self, key: str) -> AutomationRun | None: ...

    def automation_runs(self, definition_id: str | None = None) -> tuple[AutomationRun, ...]: ...
