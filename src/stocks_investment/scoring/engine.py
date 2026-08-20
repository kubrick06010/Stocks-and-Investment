"""Pure factor and composite scoring over frozen analytical contracts."""

from __future__ import annotations

from datetime import date
from math import fsum, isfinite
from typing import Iterable, Mapping

from stocks_investment.domain.research_engine import (
    AnalysisStatus,
    CompositeScore,
    FactorObservation,
    FactorScore,
    MissingDataPolicy,
)

from .normalization import LinearScale, normalize_observation


def _ordered(observations: Iterable[FactorObservation]) -> tuple[FactorObservation, ...]:
    """Return a canonical tuple so equivalent inputs produce equivalent results."""
    return tuple(sorted(
        observations,
        key=lambda item: (item.name, item.as_of, item.period, item.calculation_version,
                          item.units, item.value is None, item.value or 0.0, item.status.value),
    ))


def score_factor(
    name: str,
    observations: Iterable[FactorObservation],
    *,
    as_of: date,
    scale: LinearScale,
    weight: float = 1.0,
    version: str | None = None,
) -> FactorScore:
    """Score valid observations for one factor using their arithmetic mean.

    Non-valid observations remain attached to the result and do not become zero.
    A factor with no valid observations is unavailable and has no score.
    """
    if not name.strip():
        raise ValueError("factor name must not be empty")
    if not isfinite(weight) or weight < 0:
        raise ValueError("factor weight must be finite and non-negative")
    canonical = _ordered(observations)
    eligible = tuple(item for item in canonical if item.as_of <= as_of)
    values = [normalize_observation(item, scale) for item in eligible]
    valid_values = [value for value in values if value is not None]
    factor_version = version or f"score-v1|{scale.identity}"
    if not factor_version.strip():
        raise ValueError("factor version must not be empty")
    if not valid_values:
        status = next((item.status for item in eligible if item.status is not AnalysisStatus.VALID),
                      AnalysisStatus.INSUFFICIENT_HISTORY if canonical else AnalysisStatus.MISSING)
        return FactorScore(name, factor_version, None, status, weight, canonical,
                           f"{name}: unavailable; no valid observation on or before {as_of.isoformat()}")
    score = fsum(valid_values) / len(valid_values)
    excluded = len(canonical) - len(valid_values)
    rationale = (f"{name}: mean of {len(valid_values)} normalized observation(s) using "
                 f"{scale.identity}; {excluded} observation(s) unavailable or future")
    return FactorScore(name, factor_version, score, AnalysisStatus.VALID, weight, canonical, rationale)


def compose(
    strategy_name: str,
    strategy_version: str,
    factors: Iterable[FactorScore],
    *,
    as_of: date,
    missing_data_policy: MissingDataPolicy,
) -> CompositeScore:
    """Compose factor scores with an explicit missing-data policy."""
    if not strategy_name.strip() or not strategy_version.strip():
        raise ValueError("strategy identity must not be empty")
    components = tuple(sorted(factors, key=lambda item: item.factor_name))
    names = [component.factor_name for component in components]
    if len(names) != len(set(names)):
        raise ValueError("factor names must be unique")
    weights = {name: component.weight for name, component in zip(names, components)}
    if any(not isfinite(weight) or weight < 0 for weight in weights.values()):
        raise ValueError("factor weights must be finite and non-negative")
    total = fsum(weights.values())
    if not components or total <= 0:
        raise ValueError("at least one factor with positive total weight is required")

    available = tuple(component for component in components if component.status is AnalysisStatus.VALID
                      and component.score is not None)
    missing = tuple(component for component in components if component not in available)
    if missing and missing_data_policy in (MissingDataPolicy.FAIL, MissingDataPolicy.INSUFFICIENT_DATA):
        status = AnalysisStatus.INSUFFICIENT_HISTORY if missing_data_policy is MissingDataPolicy.INSUFFICIENT_DATA else AnalysisStatus.MISSING
        final = None
    elif not available:
        status = AnalysisStatus.INSUFFICIENT_HISTORY
        final = 0.0 if missing_data_policy is MissingDataPolicy.PENALIZE else None
    else:
        numerator = fsum(component.score * weights[component.factor_name] for component in available if component.score is not None)
        denominator = total if missing_data_policy is MissingDataPolicy.PENALIZE else fsum(weights[item.factor_name] for item in available)
        final = numerator / denominator if denominator > 0 else None
        status = AnalysisStatus.VALID if final is not None and not missing else AnalysisStatus.MISSING
    return CompositeScore(strategy_name, strategy_version, components, weights,
                           missing_data_policy, final, status, as_of)


# Descriptive alias retained for callers that prefer the result type's name.
score_composite = compose


class ScoringEngine:
    """Small adapter implementing the stable scoring-engine seam."""

    def __init__(self, scales: Mapping[str, LinearScale], *, missing_data_policy: MissingDataPolicy):
        self._scales = dict(scales)
        self.missing_data_policy = missing_data_policy

    def score_factor(self, name: str, observations: Iterable[FactorObservation], *, as_of: date) -> FactorScore:
        try:
            scale = self._scales[name]
        except KeyError as exc:
            raise KeyError(f"no normalization scale configured for factor: {name}") from exc
        return score_factor(name, observations, as_of=as_of, scale=scale)

    def compose(self, strategy_name: str, strategy_version: str, factors: Iterable[FactorScore], *, as_of: date) -> CompositeScore:
        return compose(strategy_name, strategy_version, factors, as_of=as_of,
                       missing_data_policy=self.missing_data_policy)
