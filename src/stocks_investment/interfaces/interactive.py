"""Provider-free application seam for interactive historical inspection."""

from __future__ import annotations

from typing import Protocol

from stocks_investment.domain.interactive import ResearchView, ResearchViewRequest


class InteractiveResearchService(Protocol):
    version: str

    def query(self, request: ResearchViewRequest) -> ResearchView: ...
