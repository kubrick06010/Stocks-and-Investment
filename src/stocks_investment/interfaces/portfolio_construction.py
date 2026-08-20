"""Provider-independent portfolio-construction service seam."""

from __future__ import annotations

from typing import Iterable, Protocol

from stocks_investment.domain.portfolio_construction import (
    PortfolioConstructionPolicy,
    PortfolioConstructionRequest,
    PortfolioConstructionResult,
)
from stocks_investment.domain.research import ResearchResult, ResearchRun


class PortfolioConstructor(Protocol):
    version: str

    def construct(
        self,
        request: PortfolioConstructionRequest,
        policy: PortfolioConstructionPolicy,
        run: ResearchRun,
        results: Iterable[ResearchResult],
    ) -> PortfolioConstructionResult: ...
