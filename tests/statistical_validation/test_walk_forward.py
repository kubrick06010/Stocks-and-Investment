from datetime import date

import pytest

from stocks_investment.domain import DataPartition, DateWindow, WalkForwardWindow
from stocks_investment.statistical_validation.walk_forward import (
    assign_evidence_to_partitions,
    validate_walk_forward_windows,
)


class Evidence:
    def __init__(self, key: str, as_of: date) -> None:
        self.research_run_id = key
        self.as_of = as_of


def _windows(version: str = "walk_forward_v1") -> tuple[WalkForwardWindow, ...]:
    return (
        WalkForwardWindow(
            id="w0",
            methodology_version=version,
            development=DateWindow(date(2020, 1, 1), date(2020, 3, 31)),
            validation=DateWindow(date(2020, 4, 1), date(2020, 4, 30)),
            out_of_sample=DateWindow(date(2020, 5, 1), date(2020, 5, 31)),
        ),
        WalkForwardWindow(
            id="w1",
            methodology_version=version,
            development=DateWindow(date(2020, 6, 1), date(2020, 8, 31)),
            validation=None,
            out_of_sample=DateWindow(date(2020, 9, 1), date(2020, 9, 30)),
        ),
    )


def test_validates_chronology_and_versions():
    result = validate_walk_forward_windows(_windows(), methodology_version="walk_forward_v1")
    assert result.valid
    assert result.status.value == "valid"
    assert result.errors == ()


def test_rejects_duplicate_ids_and_mixed_methodology_versions():
    first, second = _windows()
    mixed = second.__class__(
        id="w0",
        methodology_version="walk_forward_v2",
        development=second.development,
        validation=second.validation,
        out_of_sample=second.out_of_sample,
    )
    result = validate_walk_forward_windows((first, mixed))
    assert not result.valid
    assert any("IDs must be unique" in error for error in result.errors)
    assert any("one methodology version" in error for error in result.errors)


def test_rejects_overlap_attack_and_reordered_windows():
    first, second = _windows()
    overlapping = second.__class__(
        id="w1",
        methodology_version=second.methodology_version,
        development=DateWindow(date(2020, 5, 15), date(2020, 8, 31)),
        validation=None,
        out_of_sample=second.out_of_sample,
    )
    result = validate_walk_forward_windows((first, overlapping))
    assert not result.valid
    assert any("previous OOS" in error for error in result.errors)

    reordered = validate_walk_forward_windows(tuple(reversed(_windows())))
    assert not reordered.valid


def test_assigns_boundaries_once_and_keeps_oos_separate():
    records = (
        Evidence("oos", date(2020, 5, 31)),
        Evidence("dev", date(2020, 1, 1)),
        Evidence("validation", date(2020, 4, 1)),
        Evidence("outside", date(2021, 1, 1)),
    )
    result = assign_evidence_to_partitions(records, _windows())
    assigned = {item.evidence.research_run_id: item for item in result.assignments}
    assert assigned["dev"].partition is DataPartition.DEVELOPMENT
    assert assigned["validation"].partition is DataPartition.VALIDATION
    assert assigned["oos"].partition is DataPartition.OUT_OF_SAMPLE
    assert [item.evidence.research_run_id for item in result.exclusions] == ["outside"]


def test_assignment_is_deterministic_for_reordered_input():
    records = (Evidence("b", date(2020, 6, 1)), Evidence("a", date(2020, 1, 1)))
    first = assign_evidence_to_partitions(records, _windows())
    second = assign_evidence_to_partitions(tuple(reversed(records)), _windows())
    assert first == second


def test_invalid_schedule_fails_before_evidence_assignment():
    first, second = _windows()
    invalid = second.__class__(
        id="w1",
        methodology_version=second.methodology_version,
        development=DateWindow(date(2020, 5, 15), date(2020, 8, 31)),
        validation=None,
        out_of_sample=second.out_of_sample,
    )
    with pytest.raises(ValueError, match="invalid walk-forward schedule"):
        assign_evidence_to_partitions((Evidence("x", date(2020, 6, 1)),), (first, invalid))


def test_missing_date_is_explicitly_rejected_or_excluded():
    class Undated:
        research_run_id = "undated"

    with pytest.raises(ValueError, match="as_of"):
        assign_evidence_to_partitions((Undated(),), _windows())

    result = assign_evidence_to_partitions((Undated(),), _windows(), strict=False)
    assert result.exclusions[0].reason == "missing_or_invalid_as_of"
