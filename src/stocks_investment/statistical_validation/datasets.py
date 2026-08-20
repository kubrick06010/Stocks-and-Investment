"""Pure dataset-manifest validation and deterministic cohort selection.

This module deliberately operates on already-persisted
``FactorOutcomeObservation`` records.  It does not resolve providers, query
storage, or infer missing outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from stocks_investment.domain.research_intelligence import FactorOutcomeObservation
from stocks_investment.domain.statistical_validation import StatisticalDatasetManifest


class ExclusionReason(StrEnum):
    OUT_OF_WINDOW = "out_of_window"
    FACTOR_VERSION = "factor_version"
    UNIVERSE_VERSION = "universe_version"
    BENCHMARK = "benchmark"
    CURRENCY = "currency"
    MISSING_FACTOR_SCORE = "missing_factor_score"
    MISSING_OUTCOME = "missing_outcome"
    INVALID_OUTCOME_STATUS = "invalid_outcome_status"


@dataclass(frozen=True, slots=True)
class ManifestValidation:
    """Validation result for a manifest and optional observation population."""

    valid: bool
    errors: tuple[str, ...] = ()
    observation_count: int = 0
    selected_count: int = 0
    excluded_count: int = 0
    coverage: float = 0.0

    def __bool__(self) -> bool:
        return self.valid


@dataclass(frozen=True, slots=True)
class ExcludedObservation:
    observation: FactorOutcomeObservation
    reasons: tuple[ExclusionReason, ...]


@dataclass(frozen=True, slots=True)
class ObservationSelection:
    """Selected observations plus auditable exclusions and coverage."""

    observations: tuple[FactorOutcomeObservation, ...]
    exclusions: tuple[ExcludedObservation, ...]
    coverage: float

    @property
    def eligible_count(self) -> int:
        return len(self.observations)

    @property
    def excluded_count(self) -> int:
        return len(self.exclusions)


_MISSING_STATUSES = frozenset({"missing", "unavailable", "incomplete", "not_available"})
_VALID_STATUSES = frozenset({"valid", "measured", "available"})


def validate_manifest(
    manifest: StatisticalDatasetManifest,
    observations: Iterable[FactorOutcomeObservation] = (),
) -> ManifestValidation:
    """Validate manifest identity and report its observable coverage.

    The frozen domain constructor catches the minimum required identity rules.
    This function adds deterministic checks useful at dataset boundaries and
    never mutates the supplied manifest or observations.
    """

    errors: list[str] = []
    if not manifest.id.strip():
        errors.append("manifest id must not be blank")
    if not manifest.version.strip():
        errors.append("manifest version must not be blank")
    if not manifest.base_currency.strip():
        errors.append("base currency must not be blank")
    if manifest.base_currency != manifest.base_currency.upper():
        errors.append("base currency must be uppercase")
    for field_name, values in (
        ("factor_versions", manifest.factor_versions),
        ("universe_versions", manifest.universe_versions),
        ("benchmarks", manifest.benchmarks),
        ("source_snapshot_ids", manifest.source_snapshot_ids),
    ):
        if any(not value.strip() for value in values):
            errors.append(f"{field_name} must not contain blank values")
        if len(set(values)) != len(values):
            errors.append(f"{field_name} must not contain duplicates")

    population = tuple(observations)
    selection = select_observations(manifest, population)
    count = len(population)
    coverage = selection.coverage
    return ManifestValidation(
        valid=not errors,
        errors=tuple(errors),
        observation_count=count,
        selected_count=selection.eligible_count,
        excluded_count=selection.excluded_count,
        coverage=coverage,
    )


def select_observations(
    manifest: StatisticalDatasetManifest,
    observations: Iterable[FactorOutcomeObservation],
) -> ObservationSelection:
    """Select source-compatible, complete observations for ``manifest``.

    The manifest window is inclusive.  Selection is deterministic, first by
    ``as_of``, then ticker, factor name, factor version, horizon and research
    run id.  Every rejected record remains available with explicit reasons.
    """

    selected: list[FactorOutcomeObservation] = []
    exclusions: list[ExcludedObservation] = []
    population = tuple(observations)
    factor_versions = frozenset(manifest.factor_versions)
    universe_versions = frozenset(manifest.universe_versions)
    benchmarks = frozenset(manifest.benchmarks)
    currency = manifest.base_currency.upper()

    for observation in population:
        reasons: list[ExclusionReason] = []
        if not manifest.window.start <= observation.as_of <= manifest.window.end:
            reasons.append(ExclusionReason.OUT_OF_WINDOW)
        if observation.factor_version not in factor_versions:
            reasons.append(ExclusionReason.FACTOR_VERSION)
        if observation.universe not in universe_versions:
            reasons.append(ExclusionReason.UNIVERSE_VERSION)
        if observation.benchmark not in benchmarks:
            reasons.append(ExclusionReason.BENCHMARK)
        if observation.base_currency.upper() != currency:
            reasons.append(ExclusionReason.CURRENCY)
        if observation.factor_score is None:
            reasons.append(ExclusionReason.MISSING_FACTOR_SCORE)
        if any(
            value is None
            for value in (
                observation.security_return,
                observation.benchmark_return,
                observation.excess_return,
            )
        ):
            reasons.append(ExclusionReason.MISSING_OUTCOME)
        if observation.outcome_status.lower() in _MISSING_STATUSES:
            reasons.append(ExclusionReason.MISSING_OUTCOME)
        elif observation.outcome_status.lower() not in _VALID_STATUSES:
            reasons.append(ExclusionReason.INVALID_OUTCOME_STATUS)

        if reasons:
            exclusions.append(ExcludedObservation(observation, tuple(dict.fromkeys(reasons))))
        else:
            selected.append(observation)

    selected.sort(key=_observation_key)
    exclusions.sort(key=lambda item: _observation_key(item.observation))
    coverage = len(selected) / len(population) if population else 0.0
    return ObservationSelection(tuple(selected), tuple(exclusions), coverage)


def _observation_key(observation: FactorOutcomeObservation) -> tuple[object, ...]:
    return (
        observation.as_of,
        observation.ticker.symbol,
        observation.factor_name,
        observation.factor_version,
        observation.horizon,
        observation.research_run_id,
    )
