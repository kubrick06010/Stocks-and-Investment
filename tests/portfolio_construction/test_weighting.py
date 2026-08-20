from datetime import datetime, timezone
from math import inf, nan

import pytest

from stocks_investment.domain import ResearchResult, Ticker
from stocks_investment.domain.portfolio_construction import WeightingMethod
from stocks_investment.portfolio_construction.weighting import (
    EligibilityMode,
    WeightingStatus,
    build_base_weights,
)


def _result(
    ticker: str,
    *,
    run_id: str = "run-1",
    rank: int | None = 1,
    score: float | None = 80.0,
    classification: str | None = "selected",
) -> ResearchResult:
    return ResearchResult(
        id=f"{run_id}:{ticker}",
        run_id=run_id,
        ticker=Ticker(ticker),
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        rank=rank,
        composite_score=score,
        classification=classification,
    )


def test_equal_weight_is_sorted_and_independent_of_input_order() -> None:
    result = build_base_weights(
        [_result("CCC", rank=3), _result("AAA", rank=1), _result("BBB", rank=2)],
        run_id="run-1",
        method="equal_weight",
        eligibility="selected",
    )

    assert result.status is WeightingStatus.VALID
    assert [(item.ticker, item.weight) for item in result.targets] == [
        ("AAA", pytest.approx(1 / 3)),
        ("BBB", pytest.approx(1 / 3)),
        ("CCC", pytest.approx(1 / 3)),
    ]


def test_score_proportional_is_keyed_by_ticker_not_input_order() -> None:
    result = build_base_weights(
        [_result("BBB", rank=2, score=30), _result("AAA", rank=1, score=70)],
        run_id="run-1",
        method=WeightingMethod.SCORE_PROPORTIONAL,
        eligibility=EligibilityMode.RANKED,
    )

    assert result.status is WeightingStatus.VALID
    assert [item.ticker for item in result.targets] == ["AAA", "BBB"]
    assert [item.weight for item in result.targets] == [pytest.approx(0.7), pytest.approx(0.3)]


def test_selected_mode_does_not_promote_ranked_but_unselected_result() -> None:
    result = build_base_weights(
        [_result("AAA", rank=1, classification="watch"), _result("BBB", rank=2)],
        run_id="run-1",
        method="equal_weight",
        eligibility=EligibilityMode.SELECTED,
    )

    assert [item.ticker for item in result.targets] == ["BBB"]


@pytest.mark.parametrize("score", [None, 0.0, -1.0, inf, nan])
def test_score_proportional_rejects_missing_nonpositive_and_nonfinite_scores(score: float | None) -> None:
    result = build_base_weights(
        [_result("AAA", score=score), _result("BBB", rank=2, score=50)],
        run_id="run-1",
        method="score_proportional",
        eligibility="ranked",
    )

    assert result.status is WeightingStatus.INSUFFICIENT_DATA
    assert result.targets == ()
    assert result.issues[0].ticker == "AAA"


def test_mismatched_run_is_rejected_instead_of_silently_dropped() -> None:
    with pytest.raises(ValueError, match="belongs to run"):
        build_base_weights(
            [_result("AAA", run_id="other")],
            run_id="run-1",
            method="equal_weight",
            eligibility="ranked",
        )


def test_duplicate_ticker_is_rejected_even_when_input_order_differs() -> None:
    with pytest.raises(ValueError, match="unique ticker"):
        build_base_weights(
            [_result("AAA", rank=1), _result("aaa", rank=2)],
            run_id="run-1",
            method="equal_weight",
            eligibility="ranked",
        )


def test_no_eligible_results_is_explicit() -> None:
    result = build_base_weights(
        [_result("AAA", rank=None)],
        run_id="run-1",
        method="equal_weight",
        eligibility="ranked",
    )

    assert result.status is WeightingStatus.INSUFFICIENT_DATA
    assert result.issues[0].reason == "no eligible ranked results"
