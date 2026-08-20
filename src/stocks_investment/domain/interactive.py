"""Immutable contracts for the local, read-only interactive research surface."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from .research_intelligence import ResearchReport, SourceReference


class ResearchViewKind(StrEnum):
    STOCK = "stock"
    THESIS_HISTORY = "thesis_history"
    CHANGES = "changes"
    WATCHLIST = "watchlist"
    FILING = "filing"
    FILING_HISTORY = "filing_history"
    BACKTEST = "backtest"
    STRATEGY_COMPARISON = "strategy_comparison"
    FACTOR_EFFICACY = "factor_efficacy"
    AUTOMATION_RUN = "automation_run"
    PORTFOLIO_CONSTRUCTION = "portfolio_construction"


class ResearchViewStatus(StrEnum):
    VALID = "valid"
    NOT_FOUND = "not_found"
    INSUFFICIENT_DATA = "insufficient_data"
    INCOMPATIBLE = "incompatible"
    INVALID_REQUEST = "invalid_request"


class OutcomeVisibility(StrEnum):
    EXCLUDE = "exclude"
    SEPARATE = "separate"


@dataclass(frozen=True, slots=True)
class ResearchViewRequest:
    id: str
    kind: ResearchViewKind
    methodology_version: str
    primary_id: str | None = None
    secondary_id: str | None = None
    as_of: date | None = None
    factor_version: str | None = None
    horizon: str | None = None
    outcome_visibility: OutcomeVisibility = OutcomeVisibility.EXCLUDE
    limit: int = 100

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.methodology_version.strip():
            raise ValueError("interactive request identity and methodology are required")
        _safe_text(self.primary_id, "primary identifier")
        _safe_text(self.secondary_id, "secondary identifier")
        if not 1 <= self.limit <= 500:
            raise ValueError("interactive query limit must be in 1..500")
        no_primary = {ResearchViewKind.WATCHLIST}
        if self.kind not in no_primary and not self.primary_id:
            raise ValueError(f"{self.kind.value} view requires a primary identifier")
        if self.kind is ResearchViewKind.STRATEGY_COMPARISON and not self.secondary_id:
            raise ValueError("strategy comparison requires two persisted backtest identities")
        if self.kind is ResearchViewKind.FACTOR_EFFICACY:
            if not self.factor_version or not self.horizon:
                raise ValueError("factor efficacy requires explicit factor version and horizon")
            _safe_text(self.factor_version, "factor version")
            _safe_text(self.horizon, "outcome horizon")


@dataclass(frozen=True, slots=True)
class ResearchViewLink:
    label: str
    kind: ResearchViewKind
    primary_id: str | None = None
    secondary_id: str | None = None
    as_of: date | None = None

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("interactive navigation link requires a label")
        _safe_text(self.primary_id, "navigation primary identifier")
        _safe_text(self.secondary_id, "navigation secondary identifier")


@dataclass(frozen=True, slots=True)
class ResearchView:
    request_id: str
    status: ResearchViewStatus
    report: ResearchReport | None
    links: tuple[ResearchViewLink, ...]
    source_references: tuple[SourceReference, ...]
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("interactive view requires its request identity")
        if self.status is ResearchViewStatus.VALID and self.report is None:
            raise ValueError("valid interactive view requires a structured report")
        if self.status in {ResearchViewStatus.NOT_FOUND, ResearchViewStatus.INVALID_REQUEST} and self.report is not None:
            raise ValueError("missing/invalid interactive view cannot carry a report")
        identities = tuple(
            (item.entity_type, item.entity_id, item.field) for item in self.source_references
        )
        if len(identities) != len(set(identities)):
            raise ValueError("interactive view source references must be unique")


def _safe_text(value: str | None, field_name: str) -> None:
    if value is None:
        return
    if not value.strip() or any(ord(character) < 32 for character in value):
        raise ValueError(f"{field_name} must be non-empty and contain no control characters")
