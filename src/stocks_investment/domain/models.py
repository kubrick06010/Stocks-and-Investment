"""Small, immutable domain values.

These models deliberately contain no provider or persistence concerns. A financial
observation is not just a float: its period, availability, units, and evidence are
part of the value used by downstream calculations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Mapping


@dataclass(frozen=True, slots=True)
class Ticker:
    """A normalized exchange symbol."""

    symbol: str
    exchange: str | None = None

    def __post_init__(self) -> None:
        normalized = self.symbol.strip().upper()
        if not normalized:
            raise ValueError("ticker symbol must not be empty")
        object.__setattr__(self, "symbol", normalized)


@dataclass(frozen=True, slots=True)
class Period:
    """A financial reporting period, separate from data availability."""

    start: date
    end: date
    kind: str

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("period end must not precede period start")
        if not self.kind.strip():
            raise ValueError("period kind must not be empty")


@dataclass(frozen=True, slots=True)
class DataProvenance:
    """Evidence and derivation metadata for an observation."""

    source: str
    provider: str
    retrieved_at: datetime
    effective_date: date
    available_at: datetime | None = None
    filing_date: date | None = None
    period_end: date | None = None
    period: Period | None = None
    currency: str | None = None
    units: str | None = None
    raw_identifier: str | None = None
    derived: bool = False
    derivation_version: str | None = None

    def is_available_on(self, as_of: date) -> bool:
        """Return whether this evidence was public by a simulation date."""
        if self.available_at is not None and self.available_at.date() > as_of:
            return False
        if self.filing_date is not None and self.filing_date > as_of:
            return False
        return self.effective_date <= as_of


class MetricStatus(StrEnum):
    VALID = "valid"
    MISSING = "missing"
    NOT_MEANINGFUL = "not_meaningful"
    NOT_APPLICABLE = "not_applicable"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class MetricObservation:
    """A metric plus its status and source inputs."""

    name: str
    value: float | None
    status: MetricStatus
    as_of: date
    provenance: DataProvenance
    source_inputs: tuple[str, ...] = ()
    explanation: str | None = None

    def __post_init__(self) -> None:
        if self.status is MetricStatus.VALID and self.value is None:
            raise ValueError("valid metric observations require a value")
        if self.status is not MetricStatus.VALID and self.value is not None:
            raise ValueError("non-valid metric observations must not carry a value")
        if not self.provenance.is_available_on(self.as_of):
            raise ValueError("metric provenance is not available at the observation date")


@dataclass(frozen=True, slots=True)
class ScoreComponent:
    name: str
    score: float | None
    weight: float
    rationale: str
    inputs: tuple[MetricObservation, ...] = ()

    def __post_init__(self) -> None:
        if self.weight < 0:
            raise ValueError("score component weight cannot be negative")
        if self.score is not None and not 0 <= self.score <= 100:
            raise ValueError("score component must be between 0 and 100")


@dataclass(frozen=True, slots=True)
class Score:
    name: str
    value: float | None
    components: tuple[ScoreComponent, ...] = ()
    version: str = "unversioned"
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.value is not None and not 0 <= self.value <= 100:
            raise ValueError("score must be between 0 and 100")
