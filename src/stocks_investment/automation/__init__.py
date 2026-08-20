"""Deterministic research-automation control-plane helpers."""

from .orchestrator import AutomationStepFailure, DeterministicAutomationOrchestrator, StepAdapter
from .reliability import (
    ReplayDecision,
    RetryDecision,
    assert_valid_run_transition,
    canonical_idempotency_key,
    replay_decision,
    retry_decision,
    retry_delay_seconds,
    valid_run_transition,
)
from .triggers import FilingTriggerSource, ScheduledTriggerSource, build_manual_trigger

__all__ = [
    "AutomationStepFailure",
    "DeterministicAutomationOrchestrator",
    "FilingTriggerSource",
    "ReplayDecision",
    "RetryDecision",
    "ScheduledTriggerSource",
    "StepAdapter",
    "assert_valid_run_transition",
    "build_manual_trigger",
    "canonical_idempotency_key",
    "replay_decision",
    "retry_decision",
    "retry_delay_seconds",
    "valid_run_transition",
]
