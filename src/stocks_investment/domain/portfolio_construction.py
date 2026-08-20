"""Immutable contracts between persisted research signals and portfolio targets."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from math import isfinite
from typing import Mapping

from .models import Ticker
from .research_intelligence import SourceReference


class WeightingMethod(StrEnum):
    EQUAL_WEIGHT = "equal_weight"
    SCORE_PROPORTIONAL = "score_proportional"


class PortfolioConstraintKind(StrEnum):
    LONG_ONLY = "long_only"
    MAX_POSITION_WEIGHT = "max_position_weight"
    MAX_SECTOR_WEIGHT = "max_sector_weight"
    MAX_TURNOVER = "max_turnover"
    MIN_CASH_WEIGHT = "min_cash_weight"


class ConstraintStatus(StrEnum):
    SATISFIED = "satisfied"
    BINDING = "binding"
    VIOLATED = "violated"
    NOT_EVALUATED = "not_evaluated"


class ConstructionStatus(StrEnum):
    VALID = "valid"
    INFEASIBLE = "infeasible"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True, slots=True)
class PortfolioConstraint:
    kind: PortfolioConstraintKind
    limit: float | None
    version: str
    scope: str | None = None

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("portfolio constraint version is required")
        if self.kind is not PortfolioConstraintKind.LONG_ONLY:
            if self.limit is None or not isfinite(self.limit) or not 0 <= self.limit <= 1:
                raise ValueError("bounded portfolio constraints require a limit in 0..1")
        if self.kind is PortfolioConstraintKind.MAX_SECTOR_WEIGHT and not self.scope:
            raise ValueError("sector constraint requires an explicit sector scope")


@dataclass(frozen=True, slots=True)
class PortfolioConstructionPolicy:
    name: str
    version: str
    weighting_method: WeightingMethod
    constraints: tuple[PortfolioConstraint, ...]
    transaction_cost_model: str
    transaction_cost_rate: float
    allow_fractional_shares: bool
    parameters: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.version.strip() or not self.transaction_cost_model.strip():
            raise ValueError("construction policy identity and cost model are required")
        if not isfinite(self.transaction_cost_rate) or not 0 <= self.transaction_cost_rate < 1:
            raise ValueError("transaction cost rate must be in [0, 1)")
        identities = tuple((item.kind, item.scope) for item in self.constraints)
        if len(identities) != len(set(identities)):
            raise ValueError("portfolio constraints must have unique kind/scope identity")


@dataclass(frozen=True, slots=True)
class CurrentPortfolioWeight:
    ticker: Ticker
    weight: float

    def __post_init__(self) -> None:
        if not isfinite(self.weight) or not 0 <= self.weight <= 1:
            raise ValueError("current portfolio weight must be in 0..1")


@dataclass(frozen=True, slots=True)
class PortfolioConstructionRequest:
    id: str
    as_of: date
    research_run_id: str
    research_result_ids: tuple[str, ...]
    policy_name: str
    policy_version: str
    capital: float
    base_currency: str
    current_weights: tuple[CurrentPortfolioWeight, ...] = ()
    source_references: tuple[SourceReference, ...] = ()

    def __post_init__(self) -> None:
        required = (self.id, self.research_run_id, self.policy_name, self.policy_version, self.base_currency)
        if not all(value.strip() for value in required) or not isfinite(self.capital) or self.capital <= 0:
            raise ValueError("construction request identity, currency and positive capital are required")
        if not self.research_result_ids or len(self.research_result_ids) != len(set(self.research_result_ids)):
            raise ValueError("construction request requires unique research results")
        symbols = tuple(item.ticker.symbol for item in self.current_weights)
        if symbols != tuple(sorted(set(symbols))):
            raise ValueError("current portfolio weights must be unique and ticker-sorted")
        if sum(item.weight for item in self.current_weights) > 1 + 1e-9:
            raise ValueError("current portfolio weights cannot exceed 100%")


@dataclass(frozen=True, slots=True)
class TargetPosition:
    ticker: Ticker
    target_weight: float
    source_result_id: str
    source_score: float | None
    rationale: str

    def __post_init__(self) -> None:
        if not isfinite(self.target_weight) or not 0 <= self.target_weight <= 1 or not self.source_result_id.strip():
            raise ValueError("target position requires a weight in 0..1 and source result")
        if self.source_score is not None and not isfinite(self.source_score):
            raise ValueError("target source score must be finite")


@dataclass(frozen=True, slots=True)
class ConstraintEvaluation:
    kind: PortfolioConstraintKind
    scope: str | None
    observed: float | None
    limit: float | None
    status: ConstraintStatus
    rationale: str


@dataclass(frozen=True, slots=True)
class TradeEstimate:
    ticker: Ticker
    current_weight: float
    target_weight: float
    weight_delta: float
    traded_notional: float
    estimated_cost: float

    def __post_init__(self) -> None:
        values = (
            self.current_weight,
            self.target_weight,
            self.weight_delta,
            self.traded_notional,
            self.estimated_cost,
        )
        if not all(isfinite(value) for value in values):
            raise ValueError("trade estimate values must be finite")
        if self.traded_notional < 0 or self.estimated_cost < 0:
            raise ValueError("trade notional and estimated cost cannot be negative")
        if abs(self.weight_delta - (self.target_weight - self.current_weight)) > 1e-9:
            raise ValueError("trade weight delta does not reconcile")


@dataclass(frozen=True, slots=True)
class PortfolioConstructionResult:
    id: str
    request_id: str
    methodology_version: str
    status: ConstructionStatus
    targets: tuple[TargetPosition, ...]
    cash_weight: float
    gross_traded_notional: float
    turnover: float
    estimated_transaction_cost: float
    trades: tuple[TradeEstimate, ...]
    constraints: tuple[ConstraintEvaluation, ...]
    source_references: tuple[SourceReference, ...]
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.request_id.strip() or not self.methodology_version.strip():
            raise ValueError("construction result identity and methodology are required")
        symbols = tuple(item.ticker.symbol for item in self.targets)
        if symbols != tuple(sorted(set(symbols))):
            raise ValueError("target positions must be unique and ticker-sorted")
        if not isfinite(self.cash_weight) or not 0 <= self.cash_weight <= 1:
            raise ValueError("cash weight must be in 0..1")
        if self.status is ConstructionStatus.VALID:
            total = self.cash_weight + sum(item.target_weight for item in self.targets)
            if abs(total - 1) > 1e-9:
                raise ValueError("valid target weights plus cash must sum to one")
            if any(item.status is ConstraintStatus.VIOLATED for item in self.constraints):
                raise ValueError("valid construction cannot contain violated constraints")
        economic_values = (
            self.gross_traded_notional,
            self.turnover,
            self.estimated_transaction_cost,
        )
        if not all(isfinite(value) for value in economic_values):
            raise ValueError("turnover and transaction costs must be finite")
        if self.gross_traded_notional < 0 or self.turnover < 0 or self.estimated_transaction_cost < 0:
            raise ValueError("turnover and transaction costs cannot be negative")
