"""Execute the bounded real-data India PIT validation pilot offline.

This runner validates mechanics and scientific controls against the exact
CC-BY sample artifact.  It deliberately emits a ``NO_GO`` economic verdict:
17 fundamental names and a provider-defined sample benchmark cannot establish
factor profitability for the 3,838-name inventory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

from stocks_investment.domain import CohortIdentity, FactorOutcomeObservation
from stocks_investment.domain.statistical_validation import (
    DataPartition,
    DateWindow,
    FactorValidationSummary,
    SamplingMethod,
    StatisticalDatasetManifest,
    StatisticalStatus,
    StatisticalValidationRun,
    ValidationCohort,
)
from stocks_investment.factor_research.efficacy import summarize_factor
from stocks_investment.statistical_validation.artifacts import DatasetArtifactSpec
from stocks_investment.statistical_validation.datasets import select_observations
from stocks_investment.statistical_validation.india_pit import (
    BENCHMARK_VERSION,
    FACTOR_NAME,
    FACTOR_VERSION,
    UNIVERSE_VERSION,
    IndiaPitBundleSpec,
    build_india_pit_observations,
)
from stocks_investment.statistical_validation.information_coefficient import (
    calculate_cross_sectional_ic,
    summarize_ic_stability,
)
from stocks_investment.statistical_validation.sampling import DeterministicCohortSampler
from stocks_investment.statistical_validation.uncertainty import (
    moving_block_bootstrap_confidence_interval,
)
from stocks_investment.storage import SQLiteStorage


METHODOLOGY_VERSION = "india_pit_profitability_pilot_v1"
DATASET_MANIFEST_ID = "financebroski-india-pit-sample-v3"
RESEARCH_DATES = tuple(
    date(year, month, 30 if month in {6, 9} else 31)
    for year in range(2018, 2026)
    for month in (3, 6, 9, 12)
    if date(year, month, 1) >= date(2018, 6, 1)
    and date(year, month, 1) <= date(2025, 3, 1)
)

_OUTPUT_COLUMNS = (
    "research_run_id",
    "ticker",
    "as_of",
    "factor_name",
    "factor_version",
    "factor_score",
    "horizon",
    "security_return",
    "benchmark_return",
    "excess_return",
    "outcome_status",
    "universe",
    "benchmark",
    "base_currency",
    "rebalance_cadence",
)


def load_bundle_spec(manifest_path: Path, artifact_path: Path) -> IndiaPitBundleSpec:
    """Build an immutable bundle specification from the tracked acquisition manifest."""

    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = raw.get("files")
    if not isinstance(files, dict):
        raise ValueError("India PIT acquisition manifest requires a files object")
    required = {
        "fundamentals_sample.csv",
        "prices_sample.csv",
        "survivorship_universe.csv",
    }
    if set(files) != required:
        raise ValueError("India PIT acquisition manifest has an unexpected file set")
    inner_hashes: dict[str, str] = {}
    for name in sorted(required):
        record = files[name]
        if not isinstance(record, dict) or not isinstance(record.get("sha256"), str):
            raise ValueError(f"India PIT acquisition manifest has no hash for {name}")
        inner_hashes[name] = record["sha256"]
    artifact = DatasetArtifactSpec(
        artifact_path,
        _required_string(raw, "artifact_sha256"),
        _required_string(raw, "license"),
        _required_string(raw, "source_uri"),
        _required_string(raw, "snapshot_id"),
    )
    return IndiaPitBundleSpec(artifact, inner_hashes)


def run_india_pit_validation(
    spec: IndiaPitBundleSpec,
    *,
    output_directory: Path,
) -> Mapping[str, Any]:
    """Run, persist, reopen, and summarize the bounded real-data pilot."""

    output_directory.mkdir(parents=True, exist_ok=True)
    build = build_india_pit_observations(
        spec,
        research_dates=RESEARCH_DATES,
        horizons=("3M", "12M"),
    )
    derived_path = output_directory / "india-profitability-factor-outcomes-v1.csv"
    _write_observations(derived_path, build.observations)
    derived_sha256 = hashlib.sha256(derived_path.read_bytes()).hexdigest()
    manifest = StatisticalDatasetManifest(
        DATASET_MANIFEST_ID,
        "dataset_manifest_v1",
        datetime(2026, 8, 20, tzinfo=timezone.utc),
        DateWindow(RESEARCH_DATES[0], RESEARCH_DATES[-1]),
        "INR",
        (FACTOR_VERSION,),
        (UNIVERSE_VERSION,),
        (BENCHMARK_VERSION,),
        (spec.artifact.snapshot_id,),
        (
            "public artifact is a bounded sample, not the full maintained panel",
            "fundamentals cover 17 selected securities and are not representative",
            "announce_date has date-level, not timestamp-level, availability semantics",
            "latest available rows may mix consolidated and non-consolidated statements",
            "tr_close and corporate-action methodology are asserted by the publisher only",
            "terminal cash approximations are excluded from usable validation evidence",
            "equal-weight 99-security return proxy is not an authoritative market benchmark",
            "results validate machinery and do not establish factor profitability",
        ),
        {
            "artifact_sha256": build.source_sha256,
            "derived_sha256": derived_sha256,
            "license": spec.artifact.license_id,
            "source_uri": spec.artifact.source_uri,
            "pilot_verdict": "NO_GO_ECONOMIC_VALIDATION",
        },
    )
    selected = select_observations(manifest, build.observations)
    database_path = output_directory / "india-pit-validation-v1.sqlite3"
    if database_path.exists():
        raise FileExistsError(
            f"refusing to overwrite validation database: {database_path}; choose a clean output path"
        )

    horizon_results: dict[str, Mapping[str, Any]] = {}
    cohorts: list[ValidationCohort] = []
    summaries: list[FactorValidationSummary] = []
    for horizon in ("3M", "12M"):
        population = tuple(item for item in build.observations if item.horizon == horizon)
        usable = tuple(item for item in selected.observations if item.horizon == horizon)
        identity = CohortIdentity(
            FACTOR_VERSION,
            UNIVERSE_VERSION,
            RESEARCH_DATES[0],
            RESEARCH_DATES[-1],
            horizon,
            "quarterly",
            "INR",
            BENCHMARK_VERSION,
        )
        overlapping = DeterministicCohortSampler().build(
            population,
            cohort_id=f"india-profitability-{horizon.lower()}-overlapping-v1",
            dataset_manifest_id=manifest.id,
            identity=identity,
            partition=DataPartition.OUT_OF_SAMPLE,
            sampling_method=SamplingMethod.OVERLAPPING,
            minimum_sample_size=20,
            minimum_coverage=0.70,
        )
        non_overlapping = DeterministicCohortSampler().build(
            population,
            cohort_id=f"india-profitability-{horizon.lower()}-non-overlapping-v1",
            dataset_manifest_id=manifest.id,
            identity=identity,
            partition=DataPartition.OUT_OF_SAMPLE,
            sampling_method=SamplingMethod.NON_OVERLAPPING,
            minimum_sample_size=10,
            minimum_coverage=0.10,
        )
        dated_ic = calculate_cross_sectional_ic(
            usable,
            overlapping.cohort,
            minimum_observations=5,
        )
        stability = summarize_ic_stability(dated_ic, overlapping.cohort)
        valid_ic = tuple(
            (item.as_of, item.rank_ic)
            for item in dated_ic
            if item.rank_ic is not None
        )
        interval = (
            moving_block_bootstrap_confidence_interval(
                valid_ic,
                block_size=min(3, len(valid_ic)),
                confidence_level=0.95,
                resamples=2_000,
                seed=20260820,
            )
            if len(valid_ic) >= 2
            else None
        )
        efficacy = summarize_factor(usable, identity, quantiles=4)
        summary = FactorValidationSummary(
            FACTOR_NAME,
            FACTOR_VERSION,
            overlapping.cohort.id,
            METHODOLOGY_VERSION,
            stability.status,
            len(population),
            len(usable),
            len(usable) / len(population) if population else 0.0,
            dated_ic,
            interval,
            metadata={
                "pilot_only": True,
                "economic_verdict": "NO_GO",
                "non_overlapping_observations": len(non_overlapping.cohort.observation_ids),
            },
        )
        cohorts.extend((overlapping.cohort, non_overlapping.cohort))
        summaries.append(summary)
        horizon_results[horizon] = {
            "eligible_observations": len(population),
            "usable_observations": len(usable),
            "coverage": len(usable) / len(population) if population else 0.0,
            "overlapping_sample_status": overlapping.status.value,
            "non_overlapping_observations": len(non_overlapping.cohort.observation_ids),
            "non_overlapping_sample_status": non_overlapping.status.value,
            "cross_sectional_dates": stability.total_dates,
            "usable_ic_dates": stability.usable_dates,
            "mean_rank_ic": stability.mean_ic,
            "median_rank_ic": stability.median_ic,
            "rank_ic_volatility": stability.ic_volatility,
            "positive_ic_date_hit_rate": stability.positive_ic_date_hit_rate,
            "rank_ic_confidence_interval": asdict(interval) if interval is not None else None,
            "pooled_mean_security_return": efficacy.mean_forward_return,
            "pooled_mean_excess_return": efficacy.mean_excess_return,
            "pooled_top_minus_bottom_excess_spread": efficacy.spread,
            "pooled_rank_ic": efficacy.rank_ic,
            "pooled_positive_excess_hit_rate": efficacy.hit_rate,
        }

    run_status = (
        StatisticalStatus.VALID
        if all(summary.status is StatisticalStatus.VALID for summary in summaries)
        else StatisticalStatus.INSUFFICIENT_SAMPLE
    )
    run = StatisticalValidationRun(
        "india-pit-profitability-pilot-v1",
        datetime(2026, 8, 20, tzinfo=timezone.utc),
        METHODOLOGY_VERSION,
        manifest.id,
        tuple(cohort.id for cohort in cohorts),
        {
            "research_dates_csv": ",".join(value.isoformat() for value in RESEARCH_DATES),
            "horizons_csv": "3M,12M",
            "factor": "latest announced quarterly PAT / revenue percentile",
            "bootstrap_seed": 20260820,
            "bootstrap_resamples": 2_000,
        },
        run_status,
    )
    with SQLiteStorage(database_path) as storage:
        for observation in build.observations:
            storage.save_factor_outcome_observation(observation)
        storage.save_statistical_dataset_manifest(manifest)
        for cohort in cohorts:
            storage.save_validation_cohort(cohort)
        storage.save_statistical_validation_run(run)
        for summary in summaries:
            storage.save_factor_validation_summary(run.id, summary)

    with SQLiteStorage(database_path) as reopened:
        persisted_observations = reopened.load_factor_outcome_observations(
            factor_name=FACTOR_NAME,
            factor_version=FACTOR_VERSION,
        )
        if persisted_observations != build.observations:
            raise RuntimeError("India PIT observations changed across SQLite close/reopen")
        if reopened.load_statistical_dataset_manifest(manifest.id) != manifest:
            raise RuntimeError("India PIT manifest changed across SQLite close/reopen")
        if reopened.load_statistical_validation_run(run.id) != run:
            raise RuntimeError("India PIT validation run changed across SQLite close/reopen")
        expected_summaries = {item.cohort_id: item for item in summaries}
        persisted_summaries = {
            item.cohort_id: item for item in reopened.load_factor_validation_summaries(run.id)
        }
        if persisted_summaries != expected_summaries:
            raise RuntimeError("India PIT validation summaries changed across SQLite close/reopen")

    exclusion_counts = Counter(
        reason.value
        for exclusion in selected.exclusions
        for reason in exclusion.reasons
    )
    report: dict[str, Any] = {
        "verdict": "NO_GO_ECONOMIC_VALIDATION",
        "reason": (
            "real licensed sample validates the pipeline, but 17 selected fundamental names, "
            "unverified terminal returns, and a sample proxy benchmark cannot support an "
            "economic efficacy claim"
        ),
        "methodology_version": METHODOLOGY_VERSION,
        "source": {
            "uri": spec.artifact.source_uri,
            "license": spec.artifact.license_id,
            "snapshot_id": spec.artifact.snapshot_id,
            "artifact_sha256": build.source_sha256,
            "derived_sha256": derived_sha256,
        },
        "coverage": {
            "universe_inventory_securities": build.universe_securities,
            "inactive_inventory_securities": build.inactive_securities,
            "price_securities": build.price_securities,
            "fundamental_securities": build.fundamental_securities,
            "research_dates": len(build.research_dates),
            "factor_outcome_observations": len(build.observations),
            "usable_observations": len(selected.observations),
            "excluded_observations": len(selected.exclusions),
            "terminal_cash_approximations": build.terminal_cash_approximations,
            "unavailable_outcomes": build.unavailable_outcomes,
            "exclusion_reasons": dict(sorted(exclusion_counts.items())),
        },
        "horizons": horizon_results,
        "persistence": {
            "database": str(database_path),
            "close_reopen_verified": True,
            "provider_calls": 0,
        },
        "limitations": manifest.limitations,
    }
    report_path = output_directory / "india-pit-validation-v1.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )
    return report


def _write_observations(path: Path, observations: Sequence[FactorOutcomeObservation]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_OUTPUT_COLUMNS)
        writer.writeheader()
        for item in observations:
            writer.writerow(
                {
                    "research_run_id": item.research_run_id,
                    "ticker": item.ticker.symbol,
                    "as_of": item.as_of.isoformat(),
                    "factor_name": item.factor_name,
                    "factor_version": item.factor_version,
                    "factor_score": _csv_number(item.factor_score),
                    "horizon": item.horizon,
                    "security_return": _csv_number(item.security_return),
                    "benchmark_return": _csv_number(item.benchmark_return),
                    "excess_return": _csv_number(item.excess_return),
                    "outcome_status": item.outcome_status,
                    "universe": item.universe,
                    "benchmark": item.benchmark,
                    "base_currency": item.base_currency,
                    "rebalance_cadence": item.rebalance_cadence,
                }
            )


def _csv_number(value: float | None) -> str:
    return "" if value is None else repr(value)


def _required_string(values: Mapping[str, object], name: str) -> str:
    value = values.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"India PIT acquisition manifest requires {name}")
    return value


def _json_default(value: object) -> object:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("data/external/wave_e/raw/india-pit-survivorship.zip"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/manifests/india-pit-sample-v1.json"),
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("data/derived/wave_e/india-pit-pilot-v1"),
    )
    arguments = parser.parse_args(argv)
    report = run_india_pit_validation(
        load_bundle_spec(arguments.manifest, arguments.artifact),
        output_directory=arguments.output_directory,
    )
    print(json.dumps(report, indent=2, sort_keys=True, default=_json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
