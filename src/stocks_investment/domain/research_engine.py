"""Wave C contracts for explainable research and information barriers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Mapping

from stocks_investment.domain.market import PriceBar
from stocks_investment.domain.models import DataProvenance, MetricObservation, Ticker


class AnalysisStatus(StrEnum):
    VALID = "valid"
    MISSING = "missing"
    NOT_MEANINGFUL = "not_meaningful"
    INSUFFICIENT_HISTORY = "insufficient_history"
    STALE = "stale"
    NOT_APPLICABLE = "not_applicable"


class MissingDataPolicy(StrEnum):
    FAIL = "fail"
    IGNORE_AND_RENORMALIZE = "ignore_and_renormalize"
    PENALIZE = "penalize"
    INSUFFICIENT_DATA = "insufficient_data"


class CriterionStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_DATA = "insufficient_data"


class UniverseLimitation(StrEnum):
    SURVIVORSHIP_BIAS_LIMITATION = "survivorship_bias_limitation"


@dataclass(frozen=True, slots=True)
class FactorObservation:
    """An analytical input with interpretation kept separate from its value."""

    name: str
    value: float | None
    status: AnalysisStatus
    units: str
    as_of: date
    period: str
    calculation_version: str
    source_metric: str | None = None
    source_provenance: tuple[DataProvenance, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status is AnalysisStatus.VALID and self.value is None:
            raise ValueError("valid factor observations require a value")
        if self.status is not AnalysisStatus.VALID and self.value is not None:
            raise ValueError("non-valid factor observations cannot carry a value")


@dataclass(frozen=True, slots=True)
class CriterionResult:
    criterion_name: str
    criterion_version: str
    observed: float | str | None
    threshold: float | str | None
    status: CriterionStatus
    passed: bool | None
    rationale: str
    source_observations: tuple[FactorObservation, ...] = ()

    def __post_init__(self) -> None:
        if self.status is CriterionStatus.PASS and self.passed is not True:
            raise ValueError("PASS criteria must have passed=True")
        if self.status is CriterionStatus.FAIL and self.passed is not False:
            raise ValueError("FAIL criteria must have passed=False")
        if self.status in (CriterionStatus.NOT_APPLICABLE, CriterionStatus.INSUFFICIENT_DATA) and self.passed is not None:
            raise ValueError("non-decision criteria must have passed=None")


@dataclass(frozen=True, slots=True)
class FactorScore:
    factor_name: str
    factor_version: str
    score: float | None
    status: AnalysisStatus
    weight: float
    observations: tuple[FactorObservation, ...]
    rationale: str

    def __post_init__(self) -> None:
        if self.weight < 0:
            raise ValueError("factor weight cannot be negative")
        if self.score is not None and not 0 <= self.score <= 100:
            raise ValueError("factor scores must be in the range 0..100")
        if self.status is AnalysisStatus.VALID and self.score is None:
            raise ValueError("valid factor scores require a score")


@dataclass(frozen=True, slots=True)
class CompositeScore:
    strategy_name: str
    strategy_version: str
    factor_components: tuple[FactorScore, ...]
    weights: Mapping[str, float]
    missing_data_policy: MissingDataPolicy
    final_score: float | None
    status: AnalysisStatus
    as_of: date

    def __post_init__(self) -> None:
        if self.final_score is not None and not 0 <= self.final_score <= 100:
            raise ValueError("composite scores must be in the range 0..100")
        if set(self.weights) != {component.factor_name for component in self.factor_components}:
            raise ValueError("composite weights must cover exactly the factor components")


@dataclass(frozen=True, slots=True)
class UniverseSnapshot:
    name: str
    version: str
    as_of: date
    members: tuple[Ticker, ...]
    source: str
    provenance: tuple[DataProvenance, ...] = ()
    limitations: tuple[UniverseLimitation, ...] = ()

    def __post_init__(self) -> None:
        symbols = [member.symbol for member in self.members]
        if len(symbols) != len(set(symbols)):
            raise ValueError("universe members must be unique")
        if tuple(symbols) != tuple(sorted(symbols)):
            raise ValueError("universe members must be sorted for deterministic snapshots")


@dataclass(frozen=True, slots=True)
class PointInTimeDataView:
    """Read-only information barrier for a single simulation timestamp."""

    as_of: date
    metric_data: Mapping[str, tuple[MetricObservation, ...]] = field(default_factory=dict)
    price_data: tuple[PriceBar, ...] = ()

    def metric_observations(self, ticker: Ticker) -> tuple[MetricObservation, ...]:
        return tuple(
            observation for observation in self.metric_data.get(ticker.symbol, ())
            if observation.provenance.is_available_on(self.as_of)
        )

    def prices(self, ticker: Ticker, start: date, end: date) -> tuple[PriceBar, ...]:
        return tuple(
            bar for bar in self.price_data
            if bar.ticker == ticker and start <= bar.session <= end
            and bar.provenance.is_available_on(self.as_of)
        )


@dataclass(frozen=True, slots=True)
class ResearchOutcome:
    """Future information attached after a research result is frozen."""

    result_id: str
    measured_at: date
    horizon: str
    forward_return: float | None
    benchmark_return: float | None
    excess_return: float | None
