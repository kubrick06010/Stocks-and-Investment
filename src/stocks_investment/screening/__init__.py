"""Deterministic, version-aware universe screening orchestration.

The package deliberately consumes frozen Wave C records.  It does not calculate
metrics or scores and it does not provide a second persistence implementation.
"""

from .engine import (
    Candidate,
    ScreeningEngine,
    ScreeningFilter,
    ScreeningRun,
    ScreeningSelection,
)

__all__ = [
    "Candidate",
    "ScreeningEngine",
    "ScreeningFilter",
    "ScreeningRun",
    "ScreeningSelection",
]
