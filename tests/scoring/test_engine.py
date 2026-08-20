from datetime import date, timedelta

import pytest

from stocks_investment.domain import AnalysisStatus, FactorObservation, FactorScore, MissingDataPolicy
from stocks_investment.scoring import LinearScale, ScoringEngine, compose, score_factor


AS_OF = date(2025, 5, 3)


def observation(name: str, value: float | None, status: AnalysisStatus = AnalysisStatus.VALID, *, as_of: date = AS_OF) -> FactorObservation:
    return FactorObservation(name, value, status, "units", as_of, "period", "input-v1")


def test_linear_normalization_is_clipped_to_0_100_and_supports_direction() -> None:
    scale = LinearScale(0, 10)
    assert [scale.score(value) for value in (-1, 0, 5, 10, 11)] == [0.0, 0.0, 50.0, 100.0, 100.0]
    assert LinearScale(0, 10, higher_is_better=False).score(2) == 80.0


def test_non_valid_observation_is_not_coerced_to_zero() -> None:
    item = observation("quality", None, AnalysisStatus.NOT_MEANINGFUL)
    assert score_factor("quality", (item,), as_of=AS_OF, scale=LinearScale(0, 1)).score is None
    assert score_factor("quality", (item,), as_of=AS_OF, scale=LinearScale(0, 1)).status is AnalysisStatus.NOT_MEANINGFUL


def test_future_valid_observation_is_not_used() -> None:
    item = observation("quality", 1, as_of=AS_OF + timedelta(days=1))
    result = score_factor("quality", (item,), as_of=AS_OF, scale=LinearScale(0, 1))
    assert result.score is None
    assert result.status is AnalysisStatus.INSUFFICIENT_HISTORY


def test_composite_missing_data_policies_are_explicit() -> None:
    good = FactorScore("good", "v1", 80, AnalysisStatus.VALID, 1, (), "good")
    missing = FactorScore("missing", "v1", None, AnalysisStatus.MISSING, 1, (), "missing")
    assert compose("s", "v1", (good, missing), as_of=AS_OF, missing_data_policy=MissingDataPolicy.FAIL).final_score is None
    assert compose("s", "v1", (good, missing), as_of=AS_OF, missing_data_policy=MissingDataPolicy.INSUFFICIENT_DATA).final_score is None
    assert compose("s", "v1", (good, missing), as_of=AS_OF, missing_data_policy=MissingDataPolicy.IGNORE_AND_RENORMALIZE).final_score == 80
    assert compose("s", "v1", (good, missing), as_of=AS_OF, missing_data_policy=MissingDataPolicy.PENALIZE).final_score == 40


def test_weights_are_non_negative_and_positive_in_total() -> None:
    with pytest.raises(ValueError):
        FactorScore("x", "v1", 50, AnalysisStatus.VALID, -1, (), "bad")
    item = FactorScore("x", "v1", 50, AnalysisStatus.VALID, 0, (), "zero")
    with pytest.raises(ValueError):
        compose("s", "v1", (item,), as_of=AS_OF, missing_data_policy=MissingDataPolicy.FAIL)


def test_results_are_deterministic_and_carry_version_identities() -> None:
    engine = ScoringEngine({"x": LinearScale(0, 10, version="scale-v2")}, missing_data_policy=MissingDataPolicy.FAIL)
    items = (observation("x", 8), observation("x", 2))
    first = engine.score_factor("x", reversed(items), as_of=AS_OF)
    second = engine.score_factor("x", items, as_of=AS_OF)
    assert first == second
    assert first.factor_version == "score-v1|linear:scale-v2:0:10:higher"
    assert engine.compose("strategy", "strategy-v3", (first,), as_of=AS_OF).strategy_version == "strategy-v3"
