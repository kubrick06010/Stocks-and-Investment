"""Narrow provider and persistence protocols.

Concrete adapters live outside the domain and may add richer methods, but these
contracts are the stable seams used by calculations and orchestration.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable, Protocol

from stocks_investment.domain.market import PriceBar
from stocks_investment.domain.models import DataProvenance, MetricObservation, Period, Ticker
from stocks_investment.domain.research import ResearchResult, ResearchRun


class MarketDataProvider(Protocol):
    name: str

    def prices(self, ticker: Ticker, start: date, end: date) -> Iterable[PriceBar]: ...

    def provenance(self, ticker: Ticker, as_of: date) -> Iterable[DataProvenance]: ...


class FundamentalDataProvider(Protocol):
    name: str

    def metric_inputs(self, ticker: Ticker, period: Period, as_of: date) -> Iterable[MetricObservation]: ...


class UniverseProvider(Protocol):
    name: str

    def members(self, universe: str, as_of: date) -> tuple[Ticker, ...]: ...

    def version(self, universe: str, as_of: date) -> str: ...


class StorageBackend(Protocol):
    def save_observation(self, ticker: Ticker, observation: MetricObservation) -> int: ...

    def load_observations(self, ticker: Ticker, as_of: date) -> tuple[MetricObservation, ...]: ...


class ResearchStorageBackend(StorageBackend, Protocol):
    def save_research_run(self, run: ResearchRun) -> None: ...

    def save_research_result(self, result: ResearchResult) -> None: ...

    def attach_observation(self, result_id: str, observation_id: int) -> None: ...
