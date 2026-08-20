"""Scientific validation of persisted historical research outcomes."""

from .artifacts import (
    DatasetArtifact,
    DatasetArtifactSpec,
    load_factor_outcome_csv,
    validate_artifact_manifest,
)
from .datasets import ObservationSelection, select_observations, validate_manifest
from .india_pit import (
    BENCHMARK_VERSION as INDIA_PIT_BENCHMARK_VERSION,
    FACTOR_VERSION as INDIA_PIT_FACTOR_VERSION,
    UNIVERSE_VERSION as INDIA_PIT_UNIVERSE_VERSION,
    IndiaPitBuildResult,
    IndiaPitBundleSpec,
    build_india_pit_observations,
)
from .factor_dependence import (
    FactorDependenceObservation,
    FactorDependenceResult,
    FactorInteractionResult,
    calculate_factor_dependence,
    calculate_value_quality_interaction,
)
from .information_coefficient import (
    ICDecaySummary,
    ICStabilitySummary,
    calculate_cross_sectional_ic,
    calculate_ic_decay,
    summarize_ic_stability,
)
from .multiple_testing import MultipleTestingAdjusterV1, adjust_hypotheses
from .robustness import (
    RobustnessSummary,
    TurnoverAdjustedEfficacy,
    summarize_explicit_slices,
    turnover_adjusted_efficacy,
)
from .sampling import CohortSamplingResult, DeterministicCohortSampler
from .uncertainty import bootstrap_confidence_interval
from .walk_forward import assign_evidence_to_partitions, validate_walk_forward_windows

__all__ = [
    "CohortSamplingResult",
    "DeterministicCohortSampler",
    "FactorDependenceObservation",
    "FactorDependenceResult",
    "FactorInteractionResult",
    "ICDecaySummary",
    "ICStabilitySummary",
    "MultipleTestingAdjusterV1",
    "ObservationSelection",
    "RobustnessSummary",
    "TurnoverAdjustedEfficacy",
    "adjust_hypotheses",
    "assign_evidence_to_partitions",
    "bootstrap_confidence_interval",
    "calculate_cross_sectional_ic",
    "calculate_factor_dependence",
    "calculate_ic_decay",
    "calculate_value_quality_interaction",
    "select_observations",
    "summarize_explicit_slices",
    "summarize_ic_stability",
    "turnover_adjusted_efficacy",
    "validate_manifest",
    "DatasetArtifact",
    "DatasetArtifactSpec",
    "load_factor_outcome_csv",
    "validate_artifact_manifest",
    "INDIA_PIT_BENCHMARK_VERSION",
    "INDIA_PIT_FACTOR_VERSION",
    "INDIA_PIT_UNIVERSE_VERSION",
    "IndiaPitBuildResult",
    "IndiaPitBundleSpec",
    "build_india_pit_observations",
    "validate_walk_forward_windows",
]
