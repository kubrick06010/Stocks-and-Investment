"""Wave E immutable contracts for scientific validation of historical signals."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Mapping

from stocks_investment.domain.research_intelligence import CohortIdentity


class StatisticalStatus(StrEnum):
    VALID = "valid"
    INSUFFICIENT_SAMPLE = "insufficient_sample"
    INSUFFICIENT_COVERAGE = "insufficient_coverage"
    INCOMPATIBLE_COHORT = "incompatible_cohort"
    NOT_APPLICABLE = "not_applicable"


class SamplingMethod(StrEnum):
    OVERLAPPING = "overlapping"
    NON_OVERLAPPING = "non_overlapping"


class DataPartition(StrEnum):
    DEVELOPMENT = "development"
    VALIDATION = "validation"
    OUT_OF_SAMPLE = "out_of_sample"


class BootstrapMethod(StrEnum):
    IID = "iid"
    MOVING_BLOCK = "moving_block"


class MultipleTestingMethod(StrEnum):
    NONE = "none"
    BENJAMINI_HOCHBERG = "benjamini_hochberg"
    HOLM_BONFERRONI = "holm_bonferroni"


@dataclass(frozen=True, slots=True)
class DateWindow:
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("date window end must not precede start")


@dataclass(frozen=True, slots=True)
class StatisticalDatasetManifest:
    id: str
    version: str
    created_at: datetime
    window: DateWindow
    base_currency: str
    factor_versions: tuple[str, ...]
    universe_versions: tuple[str, ...]
    benchmarks: tuple[str, ...]
    source_snapshot_ids: tuple[str, ...]
    limitations: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.version or not self.base_currency:
            raise ValueError("dataset manifest identity and currency are required")
        if not self.factor_versions or not self.universe_versions or not self.benchmarks:
            raise ValueError("dataset manifest must identify factors, universes, and benchmarks")


@dataclass(frozen=True, slots=True)
class ValidationCohort:
    id: str
    dataset_manifest_id: str
    identity: CohortIdentity
    partition: DataPartition
    sampling_method: SamplingMethod
    observation_ids: tuple[int, ...]
    overlapping_horizons: bool
    minimum_sample_size: int
    minimum_coverage: float

    def __post_init__(self) -> None:
        if not self.id or not self.dataset_manifest_id:
            raise ValueError("validation cohort identity is required")
        if self.minimum_sample_size <= 0 or not 0 <= self.minimum_coverage <= 1:
            raise ValueError("invalid validation sample requirements")
        if self.sampling_method is SamplingMethod.NON_OVERLAPPING and self.overlapping_horizons:
            raise ValueError("non-overlapping cohorts cannot declare overlapping horizons")


@dataclass(frozen=True, slots=True)
class CrossSectionalICObservation:
    as_of: date
    factor_name: str
    factor_version: str
    outcome_horizon: str
    universe: str
    benchmark: str
    sample_size: int
    rank_ic: float | None
    status: StatisticalStatus

    def __post_init__(self) -> None:
        if self.sample_size < 0:
            raise ValueError("sample size cannot be negative")
        if self.rank_ic is not None and not -1 <= self.rank_ic <= 1:
            raise ValueError("rank IC must be in -1..1")
        if self.status is StatisticalStatus.VALID and self.rank_ic is None:
            raise ValueError("valid IC observations require a value")


@dataclass(frozen=True, slots=True)
class ConfidenceInterval:
    estimate: float
    lower: float
    upper: float
    confidence_level: float
    method: BootstrapMethod
    resamples: int
    block_size: int | None = None

    def __post_init__(self) -> None:
        if self.lower > self.estimate or self.estimate > self.upper:
            raise ValueError("confidence interval must contain its estimate")
        if not 0 < self.confidence_level < 1 or self.resamples <= 0:
            raise ValueError("invalid confidence interval configuration")
        if self.method is BootstrapMethod.MOVING_BLOCK and (self.block_size is None or self.block_size <= 0):
            raise ValueError("moving-block bootstrap requires a positive block size")


@dataclass(frozen=True, slots=True)
class HypothesisTestResult:
    hypothesis_id: str
    family_id: str
    raw_p_value: float
    adjusted_p_value: float
    method: MultipleTestingMethod
    alpha: float
    rejected: bool

    def __post_init__(self) -> None:
        if not all(0 <= value <= 1 for value in (self.raw_p_value, self.adjusted_p_value, self.alpha)):
            raise ValueError("p-values and alpha must be in 0..1")


@dataclass(frozen=True, slots=True)
class WalkForwardWindow:
    id: str
    methodology_version: str
    development: DateWindow
    validation: DateWindow | None
    out_of_sample: DateWindow

    def __post_init__(self) -> None:
        prior_end = self.validation.end if self.validation is not None else self.development.end
        if self.validation is not None and self.validation.start <= self.development.end:
            raise ValueError("validation must follow development without overlap")
        if self.out_of_sample.start <= prior_end:
            raise ValueError("out-of-sample window must follow all methodology-definition data")


@dataclass(frozen=True, slots=True)
class FactorValidationSummary:
    factor_name: str
    factor_version: str
    cohort_id: str
    methodology_version: str
    status: StatisticalStatus
    eligible_observations: int
    usable_observations: int
    coverage: float
    cross_sectional_ic: tuple[CrossSectionalICObservation, ...] = ()
    rank_ic_confidence_interval: ConfidenceInterval | None = None
    turnover_adjusted_spread: float | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.eligible_observations < 0 or not 0 <= self.usable_observations <= self.eligible_observations:
            raise ValueError("invalid validation observation counts")
        if not 0 <= self.coverage <= 1:
            raise ValueError("coverage must be in 0..1")


@dataclass(frozen=True, slots=True)
class StatisticalValidationRun:
    id: str
    created_at: datetime
    methodology_version: str
    dataset_manifest_id: str
    cohort_ids: tuple[str, ...]
    parameters: Mapping[str, object]
    status: StatisticalStatus
    git_commit: str | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.methodology_version or not self.dataset_manifest_id:
            raise ValueError("validation run identity and versions are required")
        if not self.cohort_ids:
            raise ValueError("validation run requires at least one frozen cohort")
