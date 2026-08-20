"""Adversarial, independent checks for Wave E statistical primitives.

These tests intentionally exercise public APIs with reordered and incomplete
inputs.  Expected values are hand-derived in the assertions; no production
helper is used to manufacture an expected result.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from stocks_investment.backtesting.engine import rebalance_metrics
from stocks_investment.domain import (
    CohortIdentity,
    DataPartition,
    DateWindow,
    FactorOutcomeObservation,
    SamplingMethod,
    Ticker,
    ValidationCohort,
    WalkForwardWindow,
)
from stocks_investment.domain.statistical_validation import (
    HypothesisTestResult,
    MultipleTestingMethod,
    StatisticalDatasetManifest,
)
from stocks_investment.statistical_validation.datasets import (
    ExclusionReason,
    select_observations,
)
from stocks_investment.statistical_validation.factor_dependence import (
    FactorDependenceObservation,
    calculate_factor_dependence,
)
from stocks_investment.statistical_validation.information_coefficient import (
    calculate_cross_sectional_ic,
)
from stocks_investment.statistical_validation.multiple_testing import adjust_hypotheses
from stocks_investment.statistical_validation.sampling import DeterministicCohortSampler
from stocks_investment.statistical_validation.uncertainty import (
    iid_bootstrap_confidence_interval,
)
from stocks_investment.statistical_validation.walk_forward import (
    assign_evidence_to_partitions,
    validate_walk_forward_windows,
)


DAY0 = date(2024, 1, 1)


def _manifest() -> StatisticalDatasetManifest:
    from datetime import datetime, timezone

    return StatisticalDatasetManifest(
        id="adversarial-dataset",
        version="v1",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        window=DateWindow(date(2024, 1, 1), date(2024, 12, 31)),
        base_currency="USD",
        factor_versions=("quality_v1",),
        universe_versions=("US@2024",),
        benchmarks=("SPY",),
        source_snapshot_ids=("snapshot-1",),
    )


def _observation(
    ticker: str,
    as_of: date,
    *,
    score: float | None = 50.0,
    outcome: float | None = 0.1,
    run_id: str | None = None,
    factor_version: str = "quality_v1",
    universe: str = "US@2024",
    benchmark: str = "SPY",
    currency: str = "USD",
    horizon: str = "3M",
) -> FactorOutcomeObservation:
    return FactorOutcomeObservation(
        factor_name="quality",
        factor_version=factor_version,
        research_run_id=run_id or f"{ticker}-{as_of.isoformat()}",
        ticker=Ticker(ticker),
        as_of=as_of,
        factor_score=score,
        horizon=horizon,
        security_return=outcome,
        benchmark_return=0.05 if outcome is not None else None,
        excess_return=(outcome - 0.05) if outcome is not None else None,
        outcome_status="valid" if outcome is not None else "missing",
        universe=universe,
        benchmark=benchmark,
        base_currency=currency,
        rebalance_cadence="quarterly",
    )


def _identity(horizon: str = "3M") -> CohortIdentity:
    return CohortIdentity(
        factor_version="quality_v1",
        universe="US@2024",
        date_start=date(2024, 1, 1),
        date_end=date(2024, 12, 31),
        outcome_horizon=horizon,
        rebalance_cadence="quarterly",
        base_currency="USD",
        benchmark="SPY",
    )


def _cohort(horizon: str = "3M") -> ValidationCohort:
    return ValidationCohort(
        id=f"quality-{horizon}",
        dataset_manifest_id="adversarial-dataset",
        identity=_identity(horizon),
        partition=DataPartition.OUT_OF_SAMPLE,
        sampling_method=SamplingMethod.OVERLAPPING,
        observation_ids=(),
        overlapping_horizons=True,
        minimum_sample_size=4,
        minimum_coverage=0.75,
    )


def test_dataset_selection_is_identity_safe_and_missing_is_not_zero() -> None:
    records = [
        _observation("CCC", date(2024, 3, 31), outcome=0.20),
        _observation("AAA", date(2024, 3, 31), outcome=0.10),
        _observation("BBB", date(2024, 3, 31), outcome=None),
    ]
    original = tuple(records)
    result = select_observations(_manifest(), records)

    assert [row.ticker.symbol for row in result.observations] == ["AAA", "CCC"]
    assert result.coverage == pytest.approx(2 / 3)
    assert result.exclusions[0].observation.ticker.symbol == "BBB"
    assert ExclusionReason.MISSING_OUTCOME in result.exclusions[0].reasons
    assert tuple(records) == original


def test_dataset_rejects_every_incompatible_identity_dimension() -> None:
    records = (
        _observation("FACTOR", DAY0, factor_version="quality_v2"),
        _observation("UNIVERSE", DAY0, universe="NASDAQ@2024"),
        _observation("BENCHMARK", DAY0, benchmark="QQQ"),
        _observation("CURRENCY", DAY0, currency="EUR"),
    )
    result = select_observations(_manifest(), records)
    reasons = {
        item.observation.ticker.symbol: set(item.reasons) for item in result.exclusions
    }
    assert ExclusionReason.FACTOR_VERSION in reasons["FACTOR"]
    assert ExclusionReason.UNIVERSE_VERSION in reasons["UNIVERSE"]
    assert ExclusionReason.BENCHMARK in reasons["BENCHMARK"]
    assert ExclusionReason.CURRENCY in reasons["CURRENCY"]


def test_sampling_non_overlap_is_per_ticker_and_order_independent() -> None:
    records = (
        _observation("AAA", date(2024, 4, 1), run_id="aaa-2"),
        _observation("BBB", date(2024, 1, 1), run_id="bbb-1"),
        _observation("AAA", date(2024, 1, 1), run_id="aaa-1"),
        _observation("AAA", date(2024, 2, 1), run_id="aaa-overlap"),
    )
    sampler = DeterministicCohortSampler()
    kwargs = dict(
        cohort_id="cohort",
        dataset_manifest_id="adversarial-dataset",
        identity=_identity(),
        partition=DataPartition.OUT_OF_SAMPLE,
        sampling_method=SamplingMethod.NON_OVERLAPPING,
        minimum_sample_size=1,
        minimum_coverage=0.0,
    )
    first = sampler.build(records, **kwargs)
    second = sampler.build(tuple(reversed(records)), **kwargs)

    # AAA's Jan and Feb windows overlap, while BBB and AAA Apr are separate.
    assert first.cohort.observation_ids == second.cohort.observation_ids
    assert len(first.cohort.observation_ids) == 3
    assert first.coverage == pytest.approx(3 / 4)


def test_sampling_rejects_horizon_mismatch_without_falling_back() -> None:
    sampler = DeterministicCohortSampler()
    result = sampler.build(
        (_observation("AAA", DAY0, horizon="12M"),),
        cohort_id="cohort",
        dataset_manifest_id="adversarial-dataset",
        identity=_identity("3M"),
        partition=DataPartition.OUT_OF_SAMPLE,
        sampling_method=SamplingMethod.OVERLAPPING,
        minimum_sample_size=1,
        minimum_coverage=0.0,
    )
    assert result.status.value == "incompatible_cohort"
    assert result.cohort.observation_ids == ()


def test_ic_joins_each_date_by_ticker_and_uses_average_ties() -> None:
    rows = tuple(
        _observation(ticker, as_of, score=score, outcome=outcome)
        for as_of, entries in (
            (date(2024, 3, 31), (("CCC", 3.0, 0.30), ("AAA", 1.0, 0.10), ("BBB", 1.0, 0.20), ("DDD", 4.0, 0.40))),
            (date(2024, 6, 30), (("BBB", 4.0, 0.10), ("AAA", 3.0, 0.20), ("DDD", 2.0, 0.30), ("CCC", 1.0, 0.40))),
        )
        for ticker, score, outcome in entries
    )
    reordered = tuple(reversed(rows))
    first = calculate_cross_sectional_ic(rows, _cohort(), minimum_observations=4)
    second = calculate_cross_sectional_ic(reordered, _cohort(), minimum_observations=4)

    # On 2024-03-31, factor ranks are 1.5, 1.5, 3, 4 and outcome ranks
    # are 1, 2, 3, 4; Pearson correlation of those ranks is sqrt(0.9).
    assert first == second
    assert first[0].rank_ic == pytest.approx(0.9486832981)
    assert first[1].rank_ic == pytest.approx(-1.0)


def test_ic_rejects_duplicate_security_identity_and_mixed_cohort() -> None:
    duplicate = (_observation("AAA", DAY0), _observation("AAA", DAY0, run_id="other"))
    with pytest.raises(ValueError, match="duplicate ticker"):
        calculate_cross_sectional_ic(duplicate, _cohort(), minimum_observations=2)
    with pytest.raises(ValueError, match="does not belong"):
        calculate_cross_sectional_ic((_observation("AAA", DAY0, benchmark="NASDAQ"),), _cohort(), minimum_observations=2)


def test_bootstrap_seed_is_deterministic_and_does_not_mutate_dates_or_values() -> None:
    observations = tuple((DAY0 + timedelta(days=i), float(i + 1)) for i in range(6))
    original = tuple(observations)
    first = iid_bootstrap_confidence_interval(
        observations, confidence_level=0.90, resamples=250, seed=123
    )
    # Reversal is intentionally invalid: dates are part of the input identity,
    # not disposable ordering metadata.
    assert first == iid_bootstrap_confidence_interval(
        observations, confidence_level=0.90, resamples=250, seed=123
    )
    assert tuple(observations) == original
    with pytest.raises(ValueError, match="ordered"):
        iid_bootstrap_confidence_interval(
            tuple(reversed(observations)), confidence_level=0.90, resamples=250, seed=123
        )


def test_multiple_testing_family_and_method_are_not_positionally_mixed() -> None:
    def result(identifier: str, p_value: float, family: str = "family-a") -> HypothesisTestResult:
        return HypothesisTestResult(
            hypothesis_id=identifier,
            family_id=family,
            raw_p_value=p_value,
            adjusted_p_value=p_value,
            method=MultipleTestingMethod.BENJAMINI_HOCHBERG,
            alpha=0.05,
            rejected=False,
        )

    inputs = [result("z", 0.01), result("a", 0.04), result("m", 0.03)]
    assert adjust_hypotheses(inputs) == adjust_hypotheses(reversed(inputs))
    with pytest.raises(ValueError, match="exactly one.*family"):
        adjust_hypotheses(inputs + [result("other", 0.02, "family-b")])


def test_walk_forward_blocks_oos_leakage_and_is_order_stable() -> None:
    windows = (
        WalkForwardWindow(
            "w0", "wf_v1", DateWindow(date(2020, 1, 1), date(2020, 3, 31)),
            DateWindow(date(2020, 4, 1), date(2020, 4, 30)),
            DateWindow(date(2020, 5, 1), date(2020, 5, 31)),
        ),
        WalkForwardWindow(
            "w1", "wf_v1", DateWindow(date(2020, 6, 1), date(2020, 8, 31)),
            None, DateWindow(date(2020, 9, 1), date(2020, 9, 30)),
        ),
    )
    evidence = (
        _observation("AAA", date(2020, 5, 31)),
        _observation("BBB", date(2020, 1, 1)),
    )
    # The helper evidence is only required to expose as_of; its other fields
    # are irrelevant to partition assignment.
    first = assign_evidence_to_partitions(evidence, windows)
    second = assign_evidence_to_partitions(tuple(reversed(evidence)), windows)
    assert first == second
    assert {item.partition for item in first.assignments} == {
        DataPartition.DEVELOPMENT, DataPartition.OUT_OF_SAMPLE
    }
    assert validate_walk_forward_windows(tuple(reversed(windows))).valid is False


def test_factor_dependence_joins_by_security_and_rejects_mixed_universe() -> None:
    left = tuple(
        FactorDependenceObservation(Ticker(ticker), DAY0, "Value", "value_v1", value, "US@2024")
        for ticker, value in (("AAA", 1.0), ("BBB", 2.0), ("CCC", 3.0))
    )
    right = tuple(
        FactorDependenceObservation(Ticker(ticker), DAY0, "Quality", "quality_v1", value, "US@2024")
        for ticker, value in (("CCC", 10.0), ("AAA", 20.0), ("BBB", 30.0))
    )
    result = calculate_factor_dependence(
        left, right, universe="US@2024", date_start=DAY0, date_end=DAY0
    )
    assert result.shared_sample_size == 3
    # Joined values are (1,20), (2,30), (3,10): ranks (1,2,3) and (2,3,1).
    assert result.spearman_correlation == pytest.approx(-0.5)
    with pytest.raises(ValueError, match="universe"):
        calculate_factor_dependence(
            left,
            tuple(row.__class__(row.ticker, row.as_of, row.factor_name, row.factor_version, row.value, "NASDAQ@2024") for row in right),
            universe="US@2024", date_start=DAY0, date_end=DAY0,
        )


def test_factor_dependence_reports_asymmetric_key_coverage_without_shifting() -> None:
    left = tuple(
        FactorDependenceObservation(Ticker(ticker), DAY0, "Value", "value_v1", value, "US@2024")
        for ticker, value in (("AAA", 1.0), ("BBB", 2.0), ("CCC", 3.0))
    )
    right = tuple(
        FactorDependenceObservation(Ticker(ticker), DAY0, "Quality", "quality_v1", value, "US@2024")
        for ticker, value in (("AAA", 10.0), ("CCC", 30.0), ("DDD", 40.0))
    )
    result = calculate_factor_dependence(
        left, right, universe="US@2024", date_start=DAY0, date_end=DAY0,
        minimum_observations=2,
    )

    # Union keys are AAA/BBB/CCC/DDD; only AAA and CCC are paired. The
    # missing BBB/DDD records must reduce coverage, never shift values.
    assert result.eligible_keys == 4
    assert result.shared_sample_size == 2
    assert result.coverage == pytest.approx(0.5)
    assert result.spearman_correlation == pytest.approx(1.0)


def test_multiple_testing_rejects_duplicate_hypothesis_identity() -> None:
    def result(p_value: float) -> HypothesisTestResult:
        return HypothesisTestResult(
            hypothesis_id="same-id",
            family_id="family-a",
            raw_p_value=p_value,
            adjusted_p_value=p_value,
            method=MultipleTestingMethod.BENJAMINI_HOCHBERG,
            alpha=0.05,
            rejected=False,
        )

    # Two records with one identity cannot be independently adjusted or
    # recovered from the result mapping without losing one hypothesis.
    with pytest.raises(ValueError, match="unique|duplicate"):
        adjust_hypotheses([result(0.01), result(0.20)])


def test_turnover_and_transaction_cost_are_identity_safe_and_hand_checkable() -> None:
    current = {"AAA": 500.0, "BBB": 300.0, "CCC": 200.0}
    target = {"AAA": 0.25, "BBB": 0.25, "DDD": 0.50}
    traded, turnover, cost, investable = rebalance_metrics(current, target, 1000.0, 0.01)

    # Hand derivation: sells 250 + 50 + 200 and buy 500 = 1,000 traded;
    # turnover is traded/pre-trade value = 1.0; cost is 1% = 10.
    assert traded == pytest.approx(1000.0)
    assert turnover == pytest.approx(1.0)
    assert cost == pytest.approx(10.0)
    assert investable == pytest.approx(990.0)

    no_trade = rebalance_metrics({"AAA": 500.0, "BBB": 500.0}, {"AAA": 0.5, "BBB": 0.5}, 1000.0, 0.01)
    assert no_trade == (0.0, 0.0, 0.0, 1000.0)


def test_rebalance_partial_turnover_charges_only_changed_identity() -> None:
    traded, turnover, cost, investable = rebalance_metrics(
        {"AAA": 500.0, "BBB": 500.0}, {"AAA": 0.5, "CCC": 0.5}, 1000.0, 0.02
    )
    # BBB is sold for 500 and CCC bought for 500: both sides count in gross
    # traded notional, so the 2% cost is 20, not 2% of all capital by accident.
    assert traded == pytest.approx(1000.0)
    assert turnover == pytest.approx(1.0)
    assert cost == pytest.approx(20.0)
    assert investable == pytest.approx(980.0)
