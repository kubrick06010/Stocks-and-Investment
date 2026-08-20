from datetime import date

import pytest

from stocks_investment.domain import Ticker
from stocks_investment.domain.statistical_validation import StatisticalStatus
from stocks_investment.statistical_validation.factor_dependence import (
    FactorDependenceObservation,
    calculate_factor_dependence,
    calculate_value_quality_interaction,
)


DAY = date(2024, 3, 31)


def _rows(name: str, version: str, values: tuple[tuple[str, float | None], ...], universe: str = "sp500@2024") -> tuple[FactorDependenceObservation, ...]:
    return tuple(FactorDependenceObservation(Ticker(symbol), DAY, name, version, value, universe) for symbol, value in values)


def test_dependence_joins_by_ticker_not_input_order_and_matches_hand_calculation() -> None:
    left = _rows("Value", "value_v1", (("AAA", 1), ("BBB", 2), ("CCC", 3)))
    right = _rows("Quality", "quality_v1", (("CCC", 10), ("AAA", 20), ("BBB", 30)))
    result = calculate_factor_dependence(left, right, universe="sp500@2024", date_start=DAY, date_end=DAY)
    assert result.status is StatisticalStatus.VALID
    assert result.shared_sample_size == 3
    # Joined order is AAA/BBB/CCC: quality ranks are 2/3/1, so rho=-0.5.
    assert result.spearman_correlation == pytest.approx(-0.5)


def test_ties_use_average_ranks_and_missing_values_are_not_zero() -> None:
    left = _rows("Value", "value_v1", (("AAA", 1), ("BBB", 1), ("CCC", 3)))
    right = (
        _rows("Quality", "quality_v1", (("AAA", 10),))[0],
        FactorDependenceObservation(
            Ticker("BBB"), DAY, "Quality", "quality_v1", None,
            "sp500@2024", StatisticalStatus.INSUFFICIENT_COVERAGE,
        ),
        _rows("Quality", "quality_v1", (("CCC", 30),))[0],
    )
    result = calculate_factor_dependence(left, right, universe="sp500@2024", date_start=DAY, date_end=DAY, minimum_observations=3)
    assert result.shared_sample_size == 2
    assert result.status is StatisticalStatus.INSUFFICIENT_COVERAGE
    assert result.spearman_correlation is None


def test_incompatible_universe_version_and_duplicate_identity_are_rejected() -> None:
    left = _rows("Value", "value_v1", (("AAA", 1),))
    with pytest.raises(ValueError, match="universe"):
        calculate_factor_dependence(left, _rows("Quality", "quality_v1", (("AAA", 2),), "nasdaq@2024"), universe="sp500@2024", date_start=DAY, date_end=DAY)
    with pytest.raises(ValueError, match="factor identities"):
        calculate_factor_dependence(left + _rows("Value", "value_v2", (("BBB", 2),)), _rows("Quality", "quality_v1", (("AAA", 2),)), universe="sp500@2024", date_start=DAY, date_end=DAY)
    with pytest.raises(ValueError, match="duplicate"):
        calculate_factor_dependence(left + left, _rows("Quality", "quality_v1", (("AAA", 2),)), universe="sp500@2024", date_start=DAY, date_end=DAY)


def test_value_quality_interaction_is_fixed_and_deterministic() -> None:
    value = _rows("Value", "value_v1", (("AAA", 80), ("BBB", 40), ("CCC", 60)))
    quality = _rows("Quality", "quality_v1", (("CCC", 50), ("AAA", 90), ("BBB", 70)))
    first = calculate_value_quality_interaction(value, quality, universe="sp500@2024", date_start=DAY, date_end=DAY)
    second = calculate_value_quality_interaction(tuple(reversed(value)), tuple(reversed(quality)), universe="sp500@2024", date_start=DAY, date_end=DAY)
    assert first.mean_interaction_score == pytest.approx((72 + 28 + 30) / 3)
    assert first == second


def test_interaction_rejects_out_of_scale_scores_and_mixed_dates() -> None:
    with pytest.raises(ValueError, match="0..100"):
        calculate_value_quality_interaction(_rows("Value", "value_v1", (("AAA", 101),)), _rows("Quality", "quality_v1", (("AAA", 80),)), universe="sp500@2024", date_start=DAY, date_end=DAY)
    later = date(2024, 6, 30)
    with pytest.raises(ValueError, match="date range"):
        calculate_factor_dependence(_rows("Value", "value_v1", (("AAA", 1),)), _rows("Quality", "quality_v1", (("AAA", 2),), "sp500@2024"), universe="sp500@2024", date_start=later, date_end=later)
