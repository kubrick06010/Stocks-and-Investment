"""Guards against using information before it was available."""

from __future__ import annotations

from datetime import date
from typing import Iterable

from stocks_investment.domain.models import DataProvenance, MetricObservation


def require_available(provenance: DataProvenance, as_of: date) -> None:
    """Raise when evidence cannot have been known at ``as_of``."""
    if not provenance.is_available_on(as_of):
        raise ValueError(
            f"provenance for {provenance.source!r} is unavailable at {as_of.isoformat()}"
        )


def filter_available(
    observations: Iterable[MetricObservation], as_of: date
) -> tuple[MetricObservation, ...]:
    """Return only observations that were available on the requested date."""
    return tuple(
        observation
        for observation in observations
        if observation.provenance.is_available_on(as_of)
    )


def previous_period(
    observations: Iterable[MetricObservation],
    *,
    name: str,
    period_end: date,
    as_of: date,
) -> MetricObservation | None:
    """Return the latest comparable prior observation visible at ``as_of``.

    This is intentionally generic: factors such as Piotroski can request a
    prior period without storage knowing anything about the factor itself.
    """
    candidates = tuple(
        observation for observation in observations
        if observation.name == name
        and observation.provenance.period_end is not None
        and observation.provenance.period_end < period_end
        and observation.provenance.is_available_on(as_of)
    )
    return max(candidates, key=lambda observation: observation.provenance.period_end or date.min, default=None)
