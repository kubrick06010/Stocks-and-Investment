from datetime import date, datetime, timezone

import pytest

from stocks_investment.domain import (
    BootstrapMethod,
    CohortIdentity,
    ConfidenceInterval,
    CrossSectionalICObservation,
    DataPartition,
    DateWindow,
    FactorValidationSummary,
    HypothesisTestResult,
    MultipleTestingMethod,
    SamplingMethod,
    StatisticalDatasetManifest,
    StatisticalStatus,
    StatisticalValidationRun,
    ValidationCohort,
    WalkForwardWindow,
)


def identity() -> CohortIdentity:
    return CohortIdentity(
        "quality_v1", "sp500@2020", date(2020, 1, 1), date(2024, 12, 31),
        "12M", "annual", "USD", "SPY_TOTAL_RETURN",
    )


def test_dataset_manifest_freezes_sources_and_identity() -> None:
    manifest = StatisticalDatasetManifest(
        "dataset-1", "dataset_v1", datetime(2025, 1, 1, tzinfo=timezone.utc),
        DateWindow(date(2010, 1, 1), date(2024, 12, 31)), "USD",
        ("quality_v1",), ("sp500@historical_v1",), ("SPY_TOTAL_RETURN",),
        ("sqlite-snapshot:abc",), ("survivorship coverage incomplete before 2010",),
    )
    assert manifest.source_snapshot_ids == ("sqlite-snapshot:abc",)
    with pytest.raises(AttributeError):
        manifest.version = "dataset_v2"  # type: ignore[misc]


def test_non_overlapping_cohort_cannot_claim_overlapping_horizons() -> None:
    with pytest.raises(ValueError, match="non-overlapping"):
        ValidationCohort(
            "c", "d", identity(), DataPartition.OUT_OF_SAMPLE,
            SamplingMethod.NON_OVERLAPPING, (1, 2), True, 20, .8,
        )


def test_cross_sectional_ic_retains_date_and_population_identity() -> None:
    observation = CrossSectionalICObservation(
        date(2024, 12, 31), "quality", "quality_v1", "12M",
        "sp500@2024-12-31", "SPY_TOTAL_RETURN", 400, .09, StatisticalStatus.VALID,
    )
    assert observation.as_of == date(2024, 12, 31)
    assert observation.universe == "sp500@2024-12-31"


def test_block_bootstrap_requires_explicit_block_size() -> None:
    with pytest.raises(ValueError, match="block size"):
        ConfidenceInterval(.05, .01, .09, .95, BootstrapMethod.MOVING_BLOCK, 1000)
    interval = ConfidenceInterval(.05, .01, .09, .95, BootstrapMethod.MOVING_BLOCK, 1000, 4)
    assert interval.lower <= interval.estimate <= interval.upper


def test_multiple_testing_result_preserves_family_and_method() -> None:
    result = HypothesisTestResult(
        "quality-12m", "factor-family-v1", .01, .04,
        MultipleTestingMethod.BENJAMINI_HOCHBERG, .05, True,
    )
    assert result.family_id == "factor-family-v1"
    assert result.method is MultipleTestingMethod.BENJAMINI_HOCHBERG


def test_walk_forward_prevents_training_data_from_overlapping_oos() -> None:
    with pytest.raises(ValueError, match="out-of-sample"):
        WalkForwardWindow(
            "wf-1", "quality_validation_v1",
            DateWindow(date(2010, 1, 1), date(2018, 12, 31)), None,
            DateWindow(date(2018, 12, 31), date(2019, 12, 31)),
        )


def test_validation_run_and_summary_are_versioned_and_decomposable() -> None:
    run = StatisticalValidationRun(
        "validation-1", datetime(2025, 1, 1, tzinfo=timezone.utc),
        "factor_validation_v1", "dataset-1", ("cohort-1",),
        {"multiple_testing": "benjamini_hochberg"}, StatisticalStatus.VALID,
    )
    ic = CrossSectionalICObservation(
        date(2024, 12, 31), "quality", "quality_v1", "12M",
        "sp500@2024", "SPY", 400, .08, StatisticalStatus.VALID,
    )
    summary = FactorValidationSummary(
        "quality", "quality_v1", "cohort-1", run.methodology_version,
        StatisticalStatus.VALID, 500, 400, .8, (ic,),
    )
    assert summary.cross_sectional_ic == (ic,)
    assert summary.methodology_version == "factor_validation_v1"
