"""Wave D immutable contracts for longitudinal research intelligence.

These are evidence-carrying records only. They do not fetch data, regenerate
historical research, render reports, or evaluate watchlists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Mapping

from stocks_investment.domain.models import Ticker


@dataclass(frozen=True, slots=True)
class SourceReference:
    entity_type: str
    entity_id: str
    field: str | None = None


class ThesisClassification(StrEnum):
    ATTRACTIVE = "attractive"
    WATCH = "watch"
    NEUTRAL = "neutral"
    OVERVALUED = "overvalued"
    DIVERGENT = "divergent"
    DETERIORATING = "deteriorating"
    INSUFFICIENT_DATA = "insufficient_data"


class ThesisDriverCategory(StrEnum):
    VALUATION = "valuation"
    QUALITY = "quality"
    GROWTH = "growth"
    FINANCIAL_HEALTH = "financial_health"
    CASH_FLOW = "cash_flow"
    DIVIDEND = "dividend"
    MOMENTUM = "momentum"
    TREND = "trend"
    RISK = "risk"
    FORENSIC = "forensic"


class DriverDirection(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


@dataclass(frozen=True, slots=True)
class ThesisDriver:
    name: str
    category: ThesisDriverCategory
    direction: DriverDirection
    importance: float
    current_state: str
    source_reference: SourceReference
    rationale: str

    def __post_init__(self) -> None:
        if not self.name.strip() or not 0 <= self.importance <= 1:
            raise ValueError("thesis driver requires a name and importance in 0..1")


@dataclass(frozen=True, slots=True)
class ThesisAssumption:
    name: str
    description: str
    status: str
    source_reference: SourceReference


@dataclass(frozen=True, slots=True)
class ThesisInvalidator:
    name: str
    condition: str
    severity: str
    source_reference: SourceReference


@dataclass(frozen=True, slots=True)
class ThesisSnapshot:
    id: str
    ticker: Ticker
    research_run_id: str
    research_result_id: str
    as_of: date
    thesis_version: str
    classification: ThesisClassification
    summary: str
    drivers: tuple[ThesisDriver, ...] = ()
    assumptions: tuple[ThesisAssumption, ...] = ()
    invalidators: tuple[ThesisInvalidator, ...] = ()
    structured_views: Mapping[str, object] = field(default_factory=dict)
    confidence: float | None = None
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.thesis_version.strip():
            raise ValueError("thesis identity and version are required")
        if self.research_run_id.strip() == "" or self.research_result_id.strip() == "":
            raise ValueError("thesis must reference its historical research artifacts")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("thesis confidence must be in 0..1")


class ChangeType(StrEnum):
    METRIC_CHANGE = "metric_change"
    FACTOR_CHANGE = "factor_change"
    CRITERION_CHANGE = "criterion_change"
    RANK_CHANGE = "rank_change"
    CLASSIFICATION_CHANGE = "classification_change"
    UNIVERSE_CHANGE = "universe_change"
    THESIS_CHANGE = "thesis_change"
    RISK_CHANGE = "risk_change"


@dataclass(frozen=True, slots=True)
class ResearchChangeEvent:
    ticker: Ticker
    from_run_id: str
    to_run_id: str
    from_as_of: date
    to_as_of: date
    change_type: ChangeType
    field: str
    old_value: object
    new_value: object
    magnitude: float | None
    materiality: str
    source_references: tuple[SourceReference, ...] = ()


class MaterialityRuleType(StrEnum):
    ABSOLUTE = "absolute"
    RELATIVE = "relative"
    STATUS_TRANSITION = "status_transition"
    RANK_MOVEMENT = "rank_movement"


@dataclass(frozen=True, slots=True)
class MaterialityRule:
    field: str
    rule_type: MaterialityRuleType
    threshold: float | None
    version: str


@dataclass(frozen=True, slots=True)
class MaterialityPolicy:
    version: str
    rules: tuple[MaterialityRule, ...]


@dataclass(frozen=True, slots=True)
class StrategyComparison:
    strategy_a: str
    strategy_b: str
    period_start: date
    period_end: date
    universe: str
    shared_run_ids: tuple[str, ...]
    agreement_rate: float | None = None
    rank_correlation: float | None = None
    top_n_overlap: float | None = None
    return_a: float | None = None
    return_b: float | None = None
    excess_return_a: float | None = None
    excess_return_b: float | None = None
    drawdown_a: float | None = None
    drawdown_b: float | None = None
    turnover_a: float | None = None
    turnover_b: float | None = None
    assumption_mismatches: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FactorOutcomeObservation:
    factor_name: str
    factor_version: str
    research_run_id: str
    ticker: Ticker
    as_of: date
    factor_score: float | None
    horizon: str
    security_return: float | None
    benchmark_return: float | None
    excess_return: float | None
    outcome_status: str
    universe: str
    benchmark: str
    base_currency: str
    rebalance_cadence: str


@dataclass(frozen=True, slots=True)
class CohortIdentity:
    factor_version: str
    universe: str
    date_start: date
    date_end: date
    outcome_horizon: str
    rebalance_cadence: str
    base_currency: str
    benchmark: str


@dataclass(frozen=True, slots=True)
class FactorEfficacySummary:
    factor_name: str
    factor_version: str
    cohort: CohortIdentity
    sample_size: int
    coverage: float
    mean_forward_return: float | None = None
    mean_excess_return: float | None = None
    median_forward_return: float | None = None
    top_quantile_return: float | None = None
    bottom_quantile_return: float | None = None
    spread: float | None = None
    rank_ic: float | None = None
    hit_rate: float | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)


class WatchlistStatus(StrEnum):
    ACTIVE = "active"
    REVIEW = "review"
    TRIGGERED = "triggered"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class WatchCondition:
    subject: str
    operator: str
    threshold: object
    version: str
    status: str = "active"


@dataclass(frozen=True, slots=True)
class WatchlistEntry:
    id: str
    ticker: Ticker
    created_at: datetime
    source_run_id: str
    source_result_id: str
    reason: str
    status: WatchlistStatus
    priority: int = 0
    tags: tuple[str, ...] = ()
    target_conditions: tuple[WatchCondition, ...] = ()
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class MonitoringEvent:
    watchlist_entry_id: str
    research_run_id: str
    as_of: date
    condition: WatchCondition
    previous_state: object
    current_state: object
    triggered: bool
    rationale: str


@dataclass(frozen=True, slots=True)
class ReportSection:
    title: str
    section_type: str
    payload: Mapping[str, object]
    source_references: tuple[SourceReference, ...] = ()


@dataclass(frozen=True, slots=True)
class ResearchReport:
    report_type: str
    as_of: date
    source_run_ids: tuple[str, ...]
    sections: tuple[ReportSection, ...]
    metadata: Mapping[str, object] = field(default_factory=dict)
