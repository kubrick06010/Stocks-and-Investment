"""Provider-independent Wave D service seams; implementations are deferred."""

from __future__ import annotations

from datetime import date
from typing import Iterable, Protocol

from stocks_investment.domain.research import ResearchResult, ResearchRun
from stocks_investment.domain.research_intelligence import (
    FactorEfficacySummary, FactorOutcomeObservation, MaterialityPolicy, MonitoringEvent,
    ResearchChangeEvent, ResearchReport, StrategyComparison, ThesisSnapshot,
    WatchlistEntry,
)


class ThesisEngine(Protocol):
    name: str
    version: str

    def generate(self, run: ResearchRun, result: ResearchResult) -> ThesisSnapshot: ...


class ChangeDetector(Protocol):
    def compare(self, earlier: ResearchResult, later: ResearchResult, *, policy: MaterialityPolicy) -> tuple[ResearchChangeEvent, ...]: ...


class StrategyComparator(Protocol):
    def compare(self, runs_a: Iterable[ResearchRun], runs_b: Iterable[ResearchRun]) -> StrategyComparison: ...


class FactorEfficacyAnalyzer(Protocol):
    def summarize(self, observations: Iterable[FactorOutcomeObservation]) -> FactorEfficacySummary: ...


class WatchlistService(Protocol):
    def evaluate(self, entry: WatchlistEntry, run: ResearchRun, result: ResearchResult) -> tuple[MonitoringEvent, ...]: ...


class ResearchReportBuilder(Protocol):
    def build(self, report_type: str, as_of: date, source_run_ids: Iterable[str]) -> ResearchReport: ...
