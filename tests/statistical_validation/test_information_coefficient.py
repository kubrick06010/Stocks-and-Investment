from datetime import date

import pytest

from stocks_investment.domain import Ticker
from stocks_investment.domain.research_intelligence import CohortIdentity, FactorOutcomeObservation
from stocks_investment.domain.statistical_validation import StatisticalStatus, ValidationCohort
from stocks_investment.statistical_validation.information_coefficient import (
    calculate_cross_sectional_ic,
    calculate_ic_decay,
    summarize_ic_stability,
)


def _cohort(horizon: str = "12M") -> ValidationCohort:
    identity = CohortIdentity(
        "quality_v1", "sp500@2024", date(2024, 1, 1), date(2024, 12, 31),
        horizon, "quarterly", "USD", "SPY_TOTAL_RETURN",
    )
    return ValidationCohort(
        f"cohort-{horizon}", "dataset-v1", identity, "out_of_sample", "overlapping",
        (), False, 3, 0.8,
    )


def _row(symbol: str, as_of: date, score: float | None, outcome: float | None, horizon: str = "12M") -> FactorOutcomeObservation:
    return FactorOutcomeObservation(
        "quality", "quality_v1", f"run-{as_of}-{symbol}", Ticker(symbol), as_of,
        score, horizon, outcome, outcome, outcome, "valid", "sp500@2024",
        "SPY_TOTAL_RETURN", "USD", "quarterly",
    )


def test_cross_sectional_ic_is_date_keyed_and_handles_average_ties() -> None:
    rows = tuple(
        _row(symbol, date(2024, 3, 31), score, outcome)
        for symbol, score, outcome in (
            ("AAA", 1.0, 10.0), ("BBB", 1.0, 20.0), ("CCC", 3.0, 30.0),
        )
    )
    result = calculate_cross_sectional_ic(rows, _cohort(), minimum_observations=3)
    assert result[0].status is StatisticalStatus.VALID
    assert result[0].rank_ic == pytest.approx(0.8660254)


def test_missing_outcomes_are_not_zero_and_mark_insufficient_coverage() -> None:
    rows = tuple(_row(symbol, date(2024, 3, 31), float(index), outcome) for index, (symbol, outcome) in enumerate(
        (("AAA", 1.0), ("BBB", None), ("CCC", 3.0)), 1
    ))
    result = calculate_cross_sectional_ic(rows, _cohort(), minimum_observations=3)
    assert result[0].sample_size == 2
    assert result[0].rank_ic is None
    assert result[0].status is StatisticalStatus.INSUFFICIENT_COVERAGE


def test_stability_aggregates_dates_equally_not_by_row_count() -> None:
    rows = tuple(
        _row(symbol, as_of, float(index), float(index if sign > 0 else 4 - index))
        for as_of, sign in ((date(2024, 3, 31), 1), (date(2024, 6, 30), -1))
        for index, symbol in enumerate(("AAA", "BBB", "CCC"), 1)
    )
    date_ic = calculate_cross_sectional_ic(rows, _cohort(), minimum_observations=3)
    summary = summarize_ic_stability(date_ic, _cohort())
    assert summary.usable_dates == 2
    assert summary.mean_ic == pytest.approx(0.0)
    assert summary.positive_ic_date_hit_rate == pytest.approx(0.5)


def test_decay_keeps_horizons_separate_and_rejects_mixed_identity() -> None:
    rows_3m = tuple(_row(symbol, date(2024, 3, 31), float(index), float(index), "3M") for index, symbol in enumerate(("AAA", "BBB", "CCC"), 1))
    rows_12m = tuple(_row(symbol, date(2024, 3, 31), float(index), float(4 - index), "12M") for index, symbol in enumerate(("AAA", "BBB", "CCC"), 1))
    result = calculate_ic_decay(
        {"3M": rows_3m, "12M": rows_12m},
        {"3M": _cohort("3M"), "12M": _cohort("12M")},
        minimum_observations=3,
    )
    assert [point.horizon for point in result.points] == ["12M", "3M"]
    assert result.points[0].summary.mean_ic == pytest.approx(-1.0)
    assert result.points[1].summary.mean_ic == pytest.approx(1.0)
    with pytest.raises(ValueError, match="cohort identity"):
        calculate_ic_decay({"3M": rows_3m, "12M": rows_12m}, {"3M": _cohort("3M"), "12M": ValidationCohort(
            "wrong", "dataset-v1", CohortIdentity("quality_v2", "sp500@2024", date(2024, 1, 1), date(2024, 12, 31), "12M", "quarterly", "USD", "SPY_TOTAL_RETURN"), "out_of_sample", "overlapping", (), False, 3, .8,
        )}, minimum_observations=3)


def test_insufficient_date_is_explicit() -> None:
    rows = tuple(_row(symbol, date(2024, 3, 31), float(index), float(index)) for index, symbol in enumerate(("AAA", "BBB"), 1))
    result = calculate_cross_sectional_ic(rows, _cohort(), minimum_observations=3)
    assert result[0].status is StatisticalStatus.INSUFFICIENT_SAMPLE
