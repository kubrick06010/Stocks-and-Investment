from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from stocks_investment.domain import CohortIdentity
from stocks_investment.domain.statistical_validation import (
    BootstrapMethod,
    DataPartition,
    DateWindow,
    FactorValidationSummary,
    HypothesisTestResult,
    MultipleTestingMethod,
    SamplingMethod,
    StatisticalDatasetManifest,
    StatisticalStatus,
    StatisticalValidationRun,
    WalkForwardWindow,
)
from stocks_investment.statistical_validation.datasets import select_observations
from stocks_investment.statistical_validation.information_coefficient import (
    calculate_cross_sectional_ic,
    summarize_ic_stability,
)
from stocks_investment.statistical_validation.factor_dependence import (
    FactorDependenceObservation,
    calculate_factor_dependence,
)
from stocks_investment.statistical_validation.multiple_testing import adjust_hypotheses
from stocks_investment.statistical_validation.robustness import (
    summarize_explicit_slices,
    turnover_adjusted_efficacy,
)
from stocks_investment.statistical_validation.sampling import DeterministicCohortSampler
from stocks_investment.statistical_validation.uncertainty import (
    moving_block_bootstrap_confidence_interval,
)
from stocks_investment.statistical_validation.walk_forward import (
    assign_evidence_to_partitions,
    validate_walk_forward_windows,
)
from stocks_investment.storage import SQLiteStorage
from tests.fixtures.wave_e.historical_factor_data import quality_outcomes


def test_persisted_historical_factor_population_validates_and_reopens(tmp_path: Path) -> None:
    path = tmp_path / "wave-e-validation.db"
    observations = quality_outcomes()
    manifest = StatisticalDatasetManifest(
        "wave-e-quality-dataset",
        "dataset_manifest_v1",
        datetime(2026, 8, 19, tzinfo=timezone.utc),
        DateWindow(date(2021, 3, 31), date(2023, 12, 31)),
        "USD",
        ("quality_v1",),
        ("synthetic-large-cap-v1",),
        ("SYNTH-BENCH",),
        tuple(f"snapshot-{index}" for index in range(12)),
        ("synthetic fixture; not evidence of economic efficacy",),
    )
    identity = CohortIdentity(
        "quality_v1",
        "synthetic-large-cap-v1",
        manifest.window.start,
        manifest.window.end,
        "12M",
        "quarterly",
        "USD",
        "SYNTH-BENCH",
    )

    with SQLiteStorage(path) as storage:
        for observation in observations:
            storage.save_factor_outcome_observation(observation)
        storage.save_statistical_dataset_manifest(manifest)

    with SQLiteStorage(path) as reopened:
        persisted = reopened.load_factor_outcome_observations(
            factor_name="quality", factor_version="quality_v1"
        )
        selection = select_observations(manifest, persisted)
        assert len(selection.observations) == 144
        assert selection.exclusions == ()
        assert selection.coverage == 1.0

        overlapping = DeterministicCohortSampler().build(
            selection.observations,
            cohort_id="quality-overlapping",
            dataset_manifest_id=manifest.id,
            identity=identity,
            partition=DataPartition.OUT_OF_SAMPLE,
            sampling_method=SamplingMethod.OVERLAPPING,
            minimum_sample_size=24,
            minimum_coverage=0.9,
        )
        non_overlapping = DeterministicCohortSampler().build(
            selection.observations,
            cohort_id="quality-non-overlapping",
            dataset_manifest_id=manifest.id,
            identity=identity,
            partition=DataPartition.OUT_OF_SAMPLE,
            sampling_method=SamplingMethod.NON_OVERLAPPING,
            minimum_sample_size=24,
            minimum_coverage=0.2,
        )
        assert overlapping.status is StatisticalStatus.VALID
        assert len(overlapping.cohort.observation_ids) == 144
        assert non_overlapping.status is StatisticalStatus.VALID
        assert len(non_overlapping.cohort.observation_ids) == 36
        assert non_overlapping.coverage == 0.25

        dated_ic = calculate_cross_sectional_ic(
            selection.observations, overlapping.cohort, minimum_observations=10
        )
        stability = summarize_ic_stability(dated_ic, overlapping.cohort)
        assert len(dated_ic) == 12
        assert stability.status is StatisticalStatus.VALID
        assert stability.usable_dates == 12
        assert stability.mean_ic is not None

        interval = moving_block_bootstrap_confidence_interval(
            tuple((item.as_of, item.rank_ic) for item in dated_ic if item.rank_ic is not None),
            block_size=3,
            confidence_level=0.95,
            resamples=400,
            seed=17,
        )
        assert interval.method is BootstrapMethod.MOVING_BLOCK
        hypotheses = tuple(
            HypothesisTestResult(
                f"quality-{index}", "wave-e-factor-family", raw, raw,
                MultipleTestingMethod.BENJAMINI_HOCHBERG, 0.05, False,
            )
            for index, raw in enumerate((0.01, 0.04, 0.20), 1)
        )
        adjusted = adjust_hypotheses(hypotheses)
        assert tuple(item.adjusted_p_value for item in adjusted) == pytest.approx((0.03, 0.06, 0.20))

        windows = tuple(
            WalkForwardWindow(
                f"wf-{year}", "walk_forward_v1",
                DateWindow(date(year, 3, 31), date(year, 6, 30)),
                DateWindow(date(year, 9, 30), date(year, 9, 30)),
                DateWindow(date(year, 12, 31), date(year, 12, 31)),
            )
            for year in (2021, 2022, 2023)
        )
        assert validate_walk_forward_windows(windows).valid
        partitioning = assign_evidence_to_partitions(selection.observations, windows)
        assert len(partitioning.assignments) == 144

        first_date = manifest.window.start
        quality_dependence = tuple(
            FactorDependenceObservation(
                item.ticker, item.as_of, "Quality", "quality_v1", item.factor_score,
                item.universe,
            )
            for item in selection.observations
            if item.as_of == first_date
        )
        value_dependence = tuple(
            FactorDependenceObservation(
                item.ticker, item.as_of, "Value", "value_v1",
                100.0 - float(item.factor_score or 0), item.universe,
            )
            for item in selection.observations
            if item.as_of == first_date
        )
        dependence = calculate_factor_dependence(
            value_dependence, quality_dependence,
            universe="synthetic-large-cap-v1", date_start=first_date, date_end=first_date,
        )
        assert dependence.spearman_correlation == -1.0

        labels = {
            (item.ticker.symbol, item.as_of): f"year-{item.as_of.year}"
            for item in selection.observations
        }
        robustness = summarize_explicit_slices(
            selection.observations, labels, minimum_sample_size=12
        )
        assert len(robustness.slices) == 3
        turnover = turnover_adjusted_efficacy(
            0.05, gross_traded_notional=40_000, portfolio_capital=100_000,
            transaction_cost_rate=0.0025,
        )
        assert turnover.net_spread == pytest.approx(0.049)
        run = StatisticalValidationRun(
            "wave-e-validation-run",
            datetime(2026, 8, 19, tzinfo=timezone.utc),
            "factor_validation_v1",
            manifest.id,
            (overlapping.cohort.id, non_overlapping.cohort.id),
            {"seed": 17, "resamples": 400, "block_size": 3},
            StatisticalStatus.VALID,
        )
        summary = FactorValidationSummary(
            "quality",
            "quality_v1",
            overlapping.cohort.id,
            run.methodology_version,
            StatisticalStatus.VALID,
            len(selection.observations),
            stability.usable_observations,
            stability.usable_observations / len(selection.observations),
            dated_ic,
            interval,
            metadata={
                "synthetic": True,
                "overlapping_horizons": True,
                "walk_forward_windows": len(windows),
                "regime_slices": len(robustness.slices),
                "turnover_adjusted_spread": turnover.net_spread,
            },
        )
        reopened.save_validation_cohort(overlapping.cohort)
        reopened.save_validation_cohort(non_overlapping.cohort)
        reopened.save_statistical_validation_run(run)
        reopened.save_factor_validation_summary(run.id, summary)

    with SQLiteStorage(path) as final:
        assert final.load_statistical_dataset_manifest(manifest.id) == manifest
        assert final.load_validation_cohort(overlapping.cohort.id) == overlapping.cohort
        assert final.load_validation_cohort(non_overlapping.cohort.id) == non_overlapping.cohort
        assert final.load_statistical_validation_run(run.id) == run
        assert final.load_factor_validation_summaries(run.id) == (summary,)
