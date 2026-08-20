"""Optional narrative boundary over deterministic structured research."""

from __future__ import annotations

from typing import Protocol

from stocks_investment.domain.narrative import NarrativeRequest, NarrativeResult


class NarrativeRenderer(Protocol):
    name: str
    version: str

    def render(self, request: NarrativeRequest) -> NarrativeResult: ...
