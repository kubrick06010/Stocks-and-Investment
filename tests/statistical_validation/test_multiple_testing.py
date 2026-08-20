from __future__ import annotations

import pytest

from stocks_investment.domain.statistical_validation import (
    HypothesisTestResult,
    MultipleTestingMethod,
)
from stocks_investment.statistical_validation.multiple_testing import (
    MultipleTestingAdjusterV1,
    adjust_hypotheses,
)


def _result(
    hypothesis_id: str,
    p_value: float,
    *,
    family: str = "family-a",
    method: MultipleTestingMethod = MultipleTestingMethod.BENJAMINI_HOCHBERG,
    alpha: float = 0.05,
) -> HypothesisTestResult:
    return HypothesisTestResult(
        hypothesis_id=hypothesis_id,
        family_id=family,
        raw_p_value=p_value,
        adjusted_p_value=p_value,
        method=method,
        alpha=alpha,
        rejected=False,
    )


def test_benjamini_hochberg_matches_hand_calculation() -> None:
    results = adjust_hypotheses(
        [_result("h1", 0.01), _result("h2", 0.04), _result("h3", 0.03), _result("h4", 0.20)]
    )

    by_id = {item.hypothesis_id: item for item in results}
    # Sorted p-values: .01, .03, .04, .20.  BH values are .04, .06, .0533,
    # .20, then reverse cumulative minima gives .04, .0533, .0533, .20.
    assert by_id["h1"].adjusted_p_value == pytest.approx(0.04)
    assert by_id["h2"].adjusted_p_value == pytest.approx(0.0533333333)
    assert by_id["h3"].adjusted_p_value == pytest.approx(0.0533333333)
    assert by_id["h4"].adjusted_p_value == pytest.approx(0.20)
    assert by_id["h1"].rejected is True


def test_holm_bonferroni_matches_hand_calculation() -> None:
    results = adjust_hypotheses(
        [_result("h1", 0.01, method=MultipleTestingMethod.HOLM_BONFERRONI),
         _result("h2", 0.04, method=MultipleTestingMethod.HOLM_BONFERRONI),
         _result("h3", 0.03, method=MultipleTestingMethod.HOLM_BONFERRONI),
         _result("h4", 0.20, method=MultipleTestingMethod.HOLM_BONFERRONI)]
    )

    by_id = {item.hypothesis_id: item for item in results}
    # Sorted p-values: .01, .03, .04, .20; adjusted values are .04, .09,
    # .08, .20, with monotonicity enforced to .04, .09, .09, .20.
    assert [by_id[key].adjusted_p_value for key in ("h1", "h3", "h2", "h4")] == pytest.approx(
        [0.04, 0.09, 0.09, 0.20]
    )


def test_none_method_passes_raw_p_values_explicitly() -> None:
    results = adjust_hypotheses(
        [_result("h1", 0.01, method=MultipleTestingMethod.NONE),
         _result("h2", 0.80, method=MultipleTestingMethod.NONE)]
    )

    assert [(item.adjusted_p_value, item.rejected) for item in results] == [(0.01, True), (0.80, False)]


def test_ties_are_deterministic_and_adjusted_values_are_bounded() -> None:
    inputs = [
        _result("z", 0.01),
        _result("a", 0.01),
        _result("m", 0.20),
    ]
    first = adjust_hypotheses(inputs)
    second = adjust_hypotheses(reversed(inputs))

    assert first == second
    ordered = sorted(first, key=lambda item: (item.raw_p_value, item.hypothesis_id))
    assert all(0 <= item.adjusted_p_value <= 1 for item in ordered)
    assert [item.adjusted_p_value for item in ordered] == sorted(
        item.adjusted_p_value for item in ordered
    )


def test_mixed_families_are_rejected() -> None:
    with pytest.raises(ValueError, match="exactly one.*family"):
        adjust_hypotheses([_result("h1", 0.01), _result("h2", 0.02, family="family-b")])


@pytest.mark.parametrize("p_value", [-0.01, 1.01, float("nan"), float("inf")])
def test_invalid_p_values_are_rejected(p_value: float) -> None:
    with pytest.raises(ValueError, match="p-value"):
        adjust_hypotheses([_result("h1", p_value)])


def test_invalid_alpha_is_rejected() -> None:
    with pytest.raises(ValueError, match="alpha"):
        adjust_hypotheses([_result("h1", 0.01, alpha=1.0)])


def test_protocol_compatible_facade_is_deterministic() -> None:
    inputs = [_result("h1", 0.01), _result("h2", 0.10)]
    assert MultipleTestingAdjusterV1().adjust(inputs) == adjust_hypotheses(inputs)
