from datetime import date

from stocks_investment.domain import (
    CohortIdentity,
    DataPartition,
    FactorOutcomeObservation,
    SamplingMethod,
    StatisticalStatus,
    Ticker,
)
from stocks_investment.statistical_validation.sampling import DeterministicCohortSampler


def _observation(
    run: str,
    ticker: str,
    as_of: date,
    *,
    score: float | None = 50.0,
    outcome_status: str = "valid",
    horizon: str = "3M",
) -> FactorOutcomeObservation:
    return FactorOutcomeObservation(
        factor_name="quality",
        factor_version="quality_v1",
        research_run_id=run,
        ticker=Ticker(ticker),
        as_of=as_of,
        factor_score=score,
        horizon=horizon,
        security_return=0.1 if score is not None else None,
        benchmark_return=0.05 if score is not None else None,
        excess_return=0.05 if score is not None else None,
        outcome_status=outcome_status,
        universe="US@2024",
        benchmark="SPY",
        base_currency="USD",
        rebalance_cadence="quarterly",
    )


def _identity() -> CohortIdentity:
    return CohortIdentity(
        factor_version="quality_v1",
        universe="US@2024",
        date_start=date(2024, 1, 1),
        date_end=date(2024, 12, 31),
        outcome_horizon="3M",
        rebalance_cadence="quarterly",
        base_currency="USD",
        benchmark="SPY",
    )


def _build(observations, method=SamplingMethod.OVERLAPPING):
    return DeterministicCohortSampler().build(
        observations,
        cohort_id="quality-2024",
        dataset_manifest_id="dataset-v1",
        identity=_identity(),
        partition=DataPartition.DEVELOPMENT,
        sampling_method=method,
        minimum_sample_size=1,
        minimum_coverage=0.75,
    )


def test_overlapping_sampling_is_sorted_and_reports_incomplete_coverage():
    observations = (
        _observation("r2", "BBB", date(2024, 6, 30)),
        _observation("r1", "AAA", date(2024, 3, 31)),
        _observation("r3", "AAA", date(2024, 6, 30), score=None),
    )
    result = _build(observations)

    assert result.status is StatisticalStatus.INSUFFICIENT_COVERAGE
    assert result.cohort.sampling_method is SamplingMethod.OVERLAPPING
    assert len(result.cohort.observation_ids) == 2
    assert result.coverage == 2 / 3
    assert len(result.excluded_observation_ids) == 1


def test_non_overlapping_sampling_uses_explicit_forward_windows_per_ticker():
    observations = (
        _observation("r3", "AAA", date(2024, 7, 1)),
        _observation("r1", "AAA", date(2024, 1, 1)),
        _observation("r2", "AAA", date(2024, 3, 31)),
        _observation("r4", "BBB", date(2024, 3, 31)),
    )
    result = _build(observations, SamplingMethod.NON_OVERLAPPING)

    assert result.status is StatisticalStatus.VALID
    assert len(result.cohort.observation_ids) == 3
    assert any("independently for each ticker" in item for item in result.limitations)


def test_non_overlapping_selection_is_independent_of_input_order():
    rows = (
        _observation("r2", "AAA", date(2024, 4, 1)),
        _observation("r1", "AAA", date(2024, 1, 1)),
        _observation("r3", "BBB", date(2024, 1, 1)),
    )
    first = _build(rows, SamplingMethod.NON_OVERLAPPING)
    second = _build(tuple(reversed(rows)), SamplingMethod.NON_OVERLAPPING)
    assert first.cohort.observation_ids == second.cohort.observation_ids


def test_mismatched_identity_is_explicitly_incompatible():
    result = _build((_observation("r1", "AAA", date(2025, 1, 1)),))

    assert result.status is StatisticalStatus.INCOMPATIBLE_COHORT
    assert result.cohort.observation_ids == ()


def test_insufficient_sample_and_coverage_are_not_silent():
    observations = (
        _observation("r1", "AAA", date(2024, 1, 1)),
        _observation("r2", "BBB", date(2024, 1, 1), score=None),
    )
    result = DeterministicCohortSampler().build(
        observations,
        cohort_id="quality-2024",
        dataset_manifest_id="dataset-v1",
        identity=_identity(),
        partition=DataPartition.VALIDATION,
        sampling_method=SamplingMethod.OVERLAPPING,
        minimum_sample_size=2,
        minimum_coverage=0.8,
    )

    assert result.status is StatisticalStatus.INSUFFICIENT_SAMPLE
    assert result.coverage == 0.5


def test_invalid_horizon_is_rejected_when_non_overlapping_sampling_needs_windows():
    with __import__("pytest").raises(ValueError, match="unsupported outcome horizon"):
        _build((_observation("r1", "AAA", date(2024, 1, 1), horizon="Q1"),), SamplingMethod.NON_OVERLAPPING)


def test_measured_outcome_status_from_wave_d_is_usable():
    result = _build(
        (_observation("r1", "AAA", date(2024, 1, 1), outcome_status="measured"),)
    )

    assert result.status is StatisticalStatus.VALID
    assert len(result.cohort.observation_ids) == 1
