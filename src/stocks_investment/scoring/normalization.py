"""Deterministic normalization of already-computed factor observations.

This module intentionally knows nothing about providers or financial metrics.  A
caller supplies the meaningful range and direction for a factor; the normalizer
only maps that value to the contract's 0..100 score range.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from stocks_investment.domain.research_engine import FactorObservation


class NormalizationMethod(StrEnum):
    LINEAR = "linear"


@dataclass(frozen=True, slots=True)
class LinearScale:
    """A fixed, versioned linear scale.

    ``lower`` maps to 0 and ``upper`` maps to 100.  Values outside the range
    are clipped, and ``higher_is_better=False`` reverses the result.
    """

    lower: float
    upper: float
    higher_is_better: bool = True
    version: str = "linear-v1"

    def __post_init__(self) -> None:
        if not isfinite(self.lower) or not isfinite(self.upper):
            raise ValueError("linear scale bounds must be finite")
        if self.lower >= self.upper:
            raise ValueError("linear scale lower bound must be below upper bound")
        if not self.version.strip():
            raise ValueError("normalization version must not be empty")

    @property
    def method(self) -> NormalizationMethod:
        return NormalizationMethod.LINEAR

    @property
    def identity(self) -> str:
        direction = "higher" if self.higher_is_better else "lower"
        return f"{self.method.value}:{self.version}:{self.lower:g}:{self.upper:g}:{direction}"

    def score(self, value: float) -> float:
        if not isfinite(value):
            raise ValueError("factor values must be finite")
        fraction = (value - self.lower) / (self.upper - self.lower)
        clipped = min(1.0, max(0.0, fraction))
        if not self.higher_is_better:
            clipped = 1.0 - clipped
        return clipped * 100.0


def normalize_observation(observation: FactorObservation, scale: LinearScale) -> float | None:
    """Normalize one observation, preserving non-valid observations as unavailable."""

    if observation.status.value != "valid":
        return None
    if observation.value is None:  # Defensive: the frozen contract also enforces this.
        return None
    return scale.score(observation.value)
