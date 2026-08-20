"""Wave C strategy, scoring, and simulation seams."""

from __future__ import annotations

from datetime import date
from typing import Iterable, Protocol

from stocks_investment.domain.market import PriceBar
from stocks_investment.domain.models import MetricObservation, Ticker
from stocks_investment.domain.research_engine import (
    CompositeScore,
    CriterionResult,
    FactorObservation,
    FactorScore,
    UniverseSnapshot,
)


class VersionedStrategy(Protocol):
    name: str
    version: str

    def evaluate(
        self, observations: Iterable[FactorObservation], *, as_of: date
    ) -> tuple[CriterionResult, ...]: ...


class ScoringEngine(Protocol):
    def score_factor(
        self, name: str, observations: Iterable[FactorObservation], *, as_of: date
    ) -> FactorScore: ...

    def compose(
        self,
        strategy_name: str,
        strategy_version: str,
        factors: Iterable[FactorScore],
        *,
        as_of: date,
    ) -> CompositeScore: ...


class BacktestDataView(Protocol):
    as_of: date

    def metric_observations(self, ticker: Ticker) -> tuple[MetricObservation, ...]: ...

    def prices(self, ticker: Ticker, start: date, end: date) -> tuple[PriceBar, ...]: ...


class UniverseSource(Protocol):
    def snapshot(self, name: str, as_of: date) -> UniverseSnapshot: ...


class PortfolioAnalytics(Protocol):
    def time_weighted_return(self, states: Iterable[object]) -> float: ...

    def money_weighted_return(self, cash_flows: Iterable[tuple[date, float]]) -> float: ...
