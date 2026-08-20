"""Deterministic validation-cohort sampling from persisted outcomes.

This module deliberately does not persist or recompute observations.  It only
selects already persisted ``FactorOutcomeObservation`` records and returns a
local sampling report plus the frozen ``ValidationCohort`` contract.
"""

from __future__ import annotations

import calendar
import hashlib
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

from stocks_investment.domain.research_intelligence import (
    CohortIdentity,
    FactorOutcomeObservation,
)
from stocks_investment.domain.statistical_validation import (
    DataPartition,
    SamplingMethod,
    StatisticalStatus,
    ValidationCohort,
)

_HORIZON_RE = re.compile(r"^(?P<amount>[1-9][0-9]*)(?P<unit>[DMY])$")
_VALID_OUTCOME_STATUSES = frozenset(
    {"valid", "measured", "available", "usable", "complete"}
)


@dataclass(frozen=True, slots=True)
class CohortSamplingResult:
    """The selected cohort and auditable sampling counts.

    ``eligible_observation_ids`` includes records with a matching cohort
    identity and date window, even when their forward outcome is incomplete.
    ``observation_ids`` are the usable records selected by the policy.
    """

    cohort: ValidationCohort
    status: StatisticalStatus
    eligible_observation_ids: tuple[int, ...]
    excluded_observation_ids: tuple[int, ...]
    coverage: float
    limitations: tuple[str, ...] = ()


class DeterministicCohortSampler:
    """Build overlapping or non-overlapping cohorts deterministically."""

    version = "cohort_sampling_v1"

    def build(
        self,
        observations: Iterable[FactorOutcomeObservation],
        *,
        cohort_id: str,
        dataset_manifest_id: str,
        identity: CohortIdentity,
        partition: DataPartition,
        sampling_method: SamplingMethod,
        minimum_sample_size: int,
        minimum_coverage: float,
    ) -> CohortSamplingResult:
        records = tuple(observations)
        if sampling_method is SamplingMethod.NON_OVERLAPPING:
            for item in records:
                _window_end(item.as_of, item.horizon)
        eligible = tuple(
            item
            for item in records
            if _matches_identity(item, identity)
        )
        usable = tuple(item for item in eligible if _is_usable(item))
        selected = (
            usable
            if sampling_method is SamplingMethod.OVERLAPPING
            else _select_non_overlapping(usable)
        )
        selected_ids = tuple(_observation_id(item) for item in selected)
        eligible_ids = tuple(_observation_id(item) for item in eligible)
        selected_id_set = frozenset(selected_ids)
        excluded_ids = tuple(
            observation_id for observation_id in eligible_ids if observation_id not in selected_id_set
        )
        coverage = len(selected) / len(eligible) if eligible else 0.0
        status = _status(
            records=records,
            eligible_count=len(eligible),
            selected_count=len(selected),
            coverage=coverage,
            minimum_sample_size=minimum_sample_size,
            minimum_coverage=minimum_coverage,
        )
        limitations = _limitations(
            records=records,
            eligible=eligible,
            selected=selected,
            sampling_method=sampling_method,
        )
        cohort = ValidationCohort(
            id=cohort_id,
            dataset_manifest_id=dataset_manifest_id,
            identity=identity,
            partition=partition,
            sampling_method=sampling_method,
            observation_ids=selected_ids,
            overlapping_horizons=sampling_method is SamplingMethod.OVERLAPPING,
            minimum_sample_size=minimum_sample_size,
            minimum_coverage=minimum_coverage,
        )
        return CohortSamplingResult(
            cohort=cohort,
            status=status,
            eligible_observation_ids=eligible_ids,
            excluded_observation_ids=excluded_ids,
            coverage=coverage,
            limitations=limitations,
        )


def build_validation_cohort(
    observations: Iterable[FactorOutcomeObservation],
    **kwargs: object,
) -> CohortSamplingResult:
    """Functional convenience wrapper around :class:`DeterministicCohortSampler`."""

    return DeterministicCohortSampler().build(observations, **kwargs)  # type: ignore[arg-type]


def _matches_identity(item: FactorOutcomeObservation, identity: CohortIdentity) -> bool:
    return (
        item.factor_version == identity.factor_version
        and item.universe == identity.universe
        and identity.date_start <= item.as_of <= identity.date_end
        and item.horizon == identity.outcome_horizon
        and item.rebalance_cadence == identity.rebalance_cadence
        and item.base_currency == identity.base_currency
        and item.benchmark == identity.benchmark
    )


def _is_usable(item: FactorOutcomeObservation) -> bool:
    return (
        item.factor_score is not None
        and item.security_return is not None
        and item.benchmark_return is not None
        and item.excess_return is not None
        and item.outcome_status.lower() in _VALID_OUTCOME_STATUSES
    )


def _observation_id(item: FactorOutcomeObservation) -> int:
    """Use the persisted run identity as the stable local observation key.

    The domain contract currently has no numeric observation ID. Include the
    factor identity as well as run/ticker/date so separate persisted factor
    observations cannot collide in a local cohort.
    """

    identity = (
        f"{item.factor_name}\x1f{item.factor_version}\x1f{item.research_run_id}"
        f"\x1f{item.ticker.symbol}\x1f{item.as_of.isoformat()}"
    )
    return int.from_bytes(hashlib.sha256(identity.encode("utf-8")).digest()[:8], "big")


def _select_non_overlapping(
    observations: tuple[FactorOutcomeObservation, ...],
) -> tuple[FactorOutcomeObservation, ...]:
    selected: list[FactorOutcomeObservation] = []
    for ticker in sorted({item.ticker.symbol for item in observations}):
        ticker_rows = sorted(
            (item for item in observations if item.ticker.symbol == ticker),
            key=lambda item: (item.as_of, item.research_run_id),
        )
        previous_end: date | None = None
        for item in ticker_rows:
            window_end = _window_end(item.as_of, item.horizon)
            if previous_end is None or item.as_of >= previous_end:
                selected.append(item)
                previous_end = window_end
    return tuple(sorted(selected, key=lambda item: (item.as_of, item.ticker.symbol, item.research_run_id)))


def _window_end(start: date, horizon: str) -> date:
    match = _HORIZON_RE.fullmatch(horizon.upper())
    if match is None:
        raise ValueError(f"unsupported outcome horizon: {horizon!r}; expected e.g. 3M or 90D")
    amount = int(match.group("amount"))
    unit = match.group("unit")
    if unit == "D":
        return start + timedelta(days=amount)
    if unit == "Y":
        return _add_months(start, amount * 12)
    return _add_months(start, amount)


def _add_months(start: date, months: int) -> date:
    zero_based_month = start.month - 1 + months
    year = start.year + zero_based_month // 12
    month = zero_based_month % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _status(
    *,
    records: tuple[FactorOutcomeObservation, ...],
    eligible_count: int,
    selected_count: int,
    coverage: float,
    minimum_sample_size: int,
    minimum_coverage: float,
) -> StatisticalStatus:
    if not records or eligible_count == 0:
        return StatisticalStatus.INCOMPATIBLE_COHORT
    if selected_count < minimum_sample_size:
        return StatisticalStatus.INSUFFICIENT_SAMPLE
    if coverage < minimum_coverage:
        return StatisticalStatus.INSUFFICIENT_COVERAGE
    return StatisticalStatus.VALID


def _limitations(
    *,
    records: tuple[FactorOutcomeObservation, ...],
    eligible: tuple[FactorOutcomeObservation, ...],
    selected: tuple[FactorOutcomeObservation, ...],
    sampling_method: SamplingMethod,
) -> tuple[str, ...]:
    limitations: list[str] = []
    if len(eligible) < len(records):
        limitations.append("records outside the requested cohort identity were excluded")
    if any(not _is_usable(item) for item in eligible):
        limitations.append("incomplete or unusable outcomes were excluded")
    if len(selected) < sum(_is_usable(item) for item in eligible):
        limitations.append("sampling policy excluded otherwise usable observations")
    if sampling_method is SamplingMethod.OVERLAPPING:
        limitations.append("forward windows may overlap and are not independent")
    else:
        limitations.append("non-overlap enforced independently for each ticker")
    return tuple(limitations)
