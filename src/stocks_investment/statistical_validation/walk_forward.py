"""Deterministic walk-forward window validation and evidence partitioning.

The functions in this module operate only on immutable, already available
records.  They do not fetch data or define a strategy.  A window is inclusive
at both ends, so adjacent windows must still have a one-day gap to avoid
sharing an observation date.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Generic, Iterable, Protocol, TypeVar

from stocks_investment.domain.statistical_validation import (
    DataPartition,
    DateWindow,
    StatisticalStatus,
    WalkForwardWindow,
)


class DatedEvidence(Protocol):
    """Minimum read-only shape required for partition assignment."""

    as_of: date


EvidenceT = TypeVar("EvidenceT", bound=DatedEvidence)


@dataclass(frozen=True, slots=True)
class WalkForwardValidation:
    """Auditable result of validating an ordered walk-forward schedule."""

    status: StatisticalStatus
    windows: tuple[WalkForwardWindow, ...]
    errors: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        return self.status is StatisticalStatus.VALID


@dataclass(frozen=True, slots=True)
class PartitionedEvidence(Generic[EvidenceT]):
    """An evidence record immutably associated with one window partition."""

    evidence: EvidenceT
    window_id: str
    partition: DataPartition


@dataclass(frozen=True, slots=True)
class EvidenceExclusion(Generic[EvidenceT]):
    evidence: EvidenceT
    reason: str


@dataclass(frozen=True, slots=True)
class EvidencePartitioning(Generic[EvidenceT]):
    """Partition assignments plus explicit records outside the schedule."""

    assignments: tuple[PartitionedEvidence[EvidenceT], ...]
    exclusions: tuple[EvidenceExclusion[EvidenceT], ...]
    status: StatisticalStatus


def validate_walk_forward_windows(
    windows: Iterable[WalkForwardWindow],
    *,
    methodology_version: str | None = None,
) -> WalkForwardValidation:
    """Validate a complete, ordered walk-forward schedule.

    Every window must use the same methodology version, have a unique ID, and
    begin strictly after the previous window's OOS end.  Strict chronology is
    intentional: with inclusive date windows, allowing equality would leak a
    date from one partition into the next.
    """

    ordered = tuple(windows)
    errors: list[str] = []
    if not ordered:
        errors.append("at least one walk-forward window is required")
    if any(not window.id for window in ordered):
        errors.append("walk-forward window IDs must not be blank")
    ids = [window.id for window in ordered]
    if len(set(ids)) != len(ids):
        errors.append("walk-forward window IDs must be unique")

    versions = {window.methodology_version for window in ordered}
    if any(not version for version in versions):
        errors.append("methodology versions must not be blank")
    if len(versions) > 1:
        errors.append("all walk-forward windows must use one methodology version")
    if methodology_version is not None and versions and versions != {methodology_version}:
        errors.append("window methodology version does not match requested version")

    previous_oos_end: date | None = None
    for index, window in enumerate(ordered):
        if previous_oos_end is not None and window.development.start <= previous_oos_end:
            errors.append(
                f"window {window.id!r} starts before the previous OOS window ends "
                f"(position {index})"
            )
        previous_oos_end = window.out_of_sample.end

    status = StatisticalStatus.VALID if not errors else StatisticalStatus.INCOMPATIBLE_COHORT
    return WalkForwardValidation(status=status, windows=ordered, errors=tuple(errors))


def assign_evidence_to_partitions(
    evidence: Iterable[EvidenceT],
    windows: Iterable[WalkForwardWindow],
    *,
    methodology_version: str | None = None,
    strict: bool = True,
) -> EvidencePartitioning[EvidenceT]:
    """Assign dated evidence to exactly one validated walk-forward partition.

    Development and validation records are methodology-definition data.  OOS
    records are therefore assigned only to ``OUT_OF_SAMPLE`` and can never be
    returned in a development or validation assignment.  Records outside the
    schedule are excluded explicitly; ``strict=True`` raises on malformed
    schedules or evidence that is not dated.
    """

    validation = validate_walk_forward_windows(
        windows,
        methodology_version=methodology_version,
    )
    if not validation.valid:
        raise ValueError("invalid walk-forward schedule: " + "; ".join(validation.errors))

    records = tuple(evidence)
    assignments: list[PartitionedEvidence[EvidenceT]] = []
    exclusions: list[EvidenceExclusion[EvidenceT]] = []
    for record in records:
        as_of = getattr(record, "as_of", None)
        if not isinstance(as_of, date):
            if strict:
                raise ValueError("walk-forward evidence must expose a date-valued as_of")
            exclusions.append(EvidenceExclusion(record, "missing_or_invalid_as_of"))
            continue
        matches = tuple(
            (window.id, partition)
            for window in validation.windows
            for partition, window_date in _partitions(window)
            if window_date.start <= as_of <= window_date.end
        )
        if len(matches) == 1:
            window_id, partition = matches[0]
            assignments.append(PartitionedEvidence(record, window_id, partition))
        elif not matches:
            exclusions.append(EvidenceExclusion(record, "outside_walk_forward_windows"))
        else:
            # This should be impossible after schedule validation, but retaining
            # the guard prevents a future contract change from creating leakage.
            raise ValueError("evidence date belongs to multiple walk-forward partitions")

    assignments.sort(key=_assignment_key)
    exclusions.sort(key=_exclusion_key)
    return EvidencePartitioning(
        assignments=tuple(assignments),
        exclusions=tuple(exclusions),
        status=StatisticalStatus.VALID,
    )


def _partitions(window: WalkForwardWindow) -> tuple[tuple[DataPartition, DateWindow], ...]:
    partitions: list[tuple[DataPartition, DateWindow]] = [
        (DataPartition.DEVELOPMENT, window.development),
    ]
    if window.validation is not None:
        partitions.append((DataPartition.VALIDATION, window.validation))
    partitions.append((DataPartition.OUT_OF_SAMPLE, window.out_of_sample))
    return tuple(partitions)


def _assignment_key(item: PartitionedEvidence[EvidenceT]) -> tuple[object, ...]:
    record = item.evidence
    return (
        record.as_of,
        item.window_id,
        item.partition.value,
        getattr(record, "research_run_id", ""),
        getattr(getattr(record, "ticker", None), "symbol", ""),
    )


def _exclusion_key(item: EvidenceExclusion[EvidenceT]) -> tuple[object, ...]:
    record = item.evidence
    as_of = getattr(record, "as_of", date.min)
    return (
        as_of,
        getattr(record, "research_run_id", ""),
        getattr(getattr(record, "ticker", None), "symbol", ""),
        item.reason,
    )


# Short aliases make the contract convenient at the service boundary while
# keeping the explicit names above as the canonical API.
validate_windows = validate_walk_forward_windows
assign_partitions = assign_evidence_to_partitions
