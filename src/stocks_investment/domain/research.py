"""Minimal persisted research-run records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Mapping

from stocks_investment.domain.models import Ticker
from stocks_investment.domain.research_engine import CriterionResult, FactorScore


class ResearchRunStatus(StrEnum):
    CREATED = "created"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ResearchRun:
    id: str
    created_at: datetime
    as_of: date
    strategy_name: str
    strategy_version: str
    universe_name: str
    universe_version: str | None = None
    universe_as_of: date | None = None
    parameters: Mapping[str, object] = field(default_factory=dict)
    git_commit: str | None = None
    data_snapshot: str | None = None
    status: ResearchRunStatus = ResearchRunStatus.CREATED


@dataclass(frozen=True, slots=True)
class ResearchResult:
    id: str
    run_id: str
    ticker: Ticker
    created_at: datetime
    rank: int | None = None
    composite_score: float | None = None
    classification: str | None = None
    factor_scores: tuple[FactorScore, ...] = ()
    criteria: tuple[CriterionResult, ...] = ()
    source_observation_ids: tuple[int, ...] = ()
