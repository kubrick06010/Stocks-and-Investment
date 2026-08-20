from datetime import date, datetime, timezone

from stocks_investment.domain import CohortIdentity
from stocks_investment.domain.statistical_validation import (
    BootstrapMethod,
    ConfidenceInterval,
    CrossSectionalICObservation,
    DataPartition,
    DateWindow,
    FactorValidationSummary,
    SamplingMethod,
    StatisticalDatasetManifest,
    StatisticalStatus,
    StatisticalValidationRun,
    ValidationCohort,
)
from stocks_investment.storage import SQLiteStorage


def test_wave_e_statistical_evidence_round_trips_after_reopen(tmp_path) -> None:
    path = tmp_path / "wave-e.db"
    manifest = StatisticalDatasetManifest(
        "dataset-1",
        "dataset_manifest_v1",
        datetime(2026, 8, 19, tzinfo=timezone.utc),
        DateWindow(date(2020, 1, 1), date(2025, 12, 31)),
        "USD",
        ("quality_v1",),
        ("sp500-historical-v1",),
        ("SPY",),
        ("snapshot-1", "snapshot-2"),
        ("delisting coverage incomplete",),
        {"source": "fixture"},
    )
    cohort = ValidationCohort(
        "cohort-1",
        manifest.id,
        CohortIdentity(
            "quality_v1",
            "sp500-historical-v1",
            date(2020, 1, 1),
            date(2025, 12, 31),
            "12M",
            "annual",
            "USD",
            "SPY",
        ),
        DataPartition.OUT_OF_SAMPLE,
        SamplingMethod.NON_OVERLAPPING,
        (10, 20, 30),
        False,
        3,
        0.8,
    )
    run = StatisticalValidationRun(
        "validation-1",
        datetime(2026, 8, 19, tzinfo=timezone.utc),
        "factor_validation_v1",
        manifest.id,
        (cohort.id,),
        {"seed": 7, "resamples": 1000},
        StatisticalStatus.VALID,
        "deadbeef",
    )
    summary = FactorValidationSummary(
        "quality",
        "quality_v1",
        cohort.id,
        run.methodology_version,
        StatisticalStatus.VALID,
        3,
        3,
        1.0,
        (
            CrossSectionalICObservation(
                date(2024, 12, 31),
                "quality",
                "quality_v1",
                "12M",
                "sp500-historical-v1",
                "SPY",
                3,
                0.5,
                StatisticalStatus.VALID,
            ),
        ),
        ConfidenceInterval(0.5, 0.1, 0.8, 0.95, BootstrapMethod.MOVING_BLOCK, 1000, 2),
        0.03,
        {"overlapping_horizons": False},
    )

    with SQLiteStorage(path) as storage:
        storage.save_statistical_dataset_manifest(manifest)
        storage.save_validation_cohort(cohort)
        storage.save_statistical_validation_run(run)
        storage.save_factor_validation_summary(run.id, summary)

    with SQLiteStorage(path) as reopened:
        assert reopened.load_statistical_dataset_manifest(manifest.id) == manifest
        assert reopened.load_validation_cohort(cohort.id) == cohort
        assert reopened.load_statistical_validation_run(run.id) == run
        assert reopened.load_factor_validation_summaries(run.id) == (summary,)
