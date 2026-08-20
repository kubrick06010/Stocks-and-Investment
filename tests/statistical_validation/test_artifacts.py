import hashlib
from datetime import date, datetime, timezone

import pytest

from stocks_investment.statistical_validation.artifacts import (
    DatasetArtifactSpec,
    load_factor_outcome_csv,
    validate_artifact_manifest,
)
from stocks_investment.domain.statistical_validation import DateWindow, StatisticalDatasetManifest


_HEADER = (
    "research_run_id,ticker,as_of,factor_name,factor_version,factor_score,horizon,"
    "security_return,benchmark_return,excess_return,outcome_status,universe,benchmark,"
    "base_currency,rebalance_cadence\n"
)


def _write(path, body: str) -> str:
    path.write_text(_HEADER + body, encoding="utf-8", newline="")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _spec(path, digest: str, **overrides) -> DatasetArtifactSpec:
    values = {
        "path": path,
        "sha256": digest,
        "license_id": "fixture-license-v1",
        "source_uri": "https://data.example.test/snapshot.csv",
        "snapshot_id": "snapshot-2026-01",
        **overrides,
    }
    return DatasetArtifactSpec(**values)


def test_hash_pinned_artifact_preserves_missing_values_and_sorts_identity(tmp_path) -> None:
    path = tmp_path / "observations.csv"
    digest = _write(
        path,
        "run-b,BBB,2024-06-30,quality,quality_v1,70,12M,0.2,0.05,0.15,valid,SP500@2024,SPY,USD,quarterly\n"
        "run-a,AAA,2024-03-31,quality,quality_v1,,12M,,, ,missing,SP500@2024,SPY,USD,quarterly\n".replace(", ,", ",,"),
    )

    artifact = load_factor_outcome_csv(_spec(path, digest))

    assert [item.ticker.symbol for item in artifact.observations] == ["AAA", "BBB"]
    assert artifact.observations[0].factor_score is None
    assert artifact.observations[0].security_return is None
    assert artifact.sha256 == digest
    assert artifact.snapshot_id == "snapshot-2026-01"


def test_hash_mismatch_and_missing_license_are_rejected(tmp_path) -> None:
    path = tmp_path / "observations.csv"
    digest = _write(path, "run-a,AAA,2024-03-31,quality,quality_v1,70,12M,0.1,0.05,0.05,valid,SP500@2024,SPY,USD,quarterly\n")
    with pytest.raises(ValueError, match="sha256"):
        load_factor_outcome_csv(_spec(path, "0" * 64))
    with pytest.raises(ValueError, match="license"):
        DatasetArtifactSpec(path, digest, "", "https://data.example.test/snapshot.csv", "snapshot")


def test_duplicate_identity_nonfinite_value_and_column_drift_are_rejected(tmp_path) -> None:
    path = tmp_path / "observations.csv"
    row = "run-a,AAA,2024-03-31,quality,quality_v1,70,12M,0.1,0.05,0.05,valid,SP500@2024,SPY,USD,quarterly\n"
    digest = _write(path, row + row)
    with pytest.raises(ValueError, match="duplicate"):
        load_factor_outcome_csv(_spec(path, digest))

    nonfinite = tmp_path / "nonfinite.csv"
    digest = _write(nonfinite, row.replace(",70,", ",nan,"))
    with pytest.raises(ValueError, match="finite"):
        load_factor_outcome_csv(_spec(nonfinite, digest))

    drift = tmp_path / "drift.csv"
    drift.write_text("ticker,as_of\nAAA,2024-03-31\n", encoding="utf-8")
    digest = hashlib.sha256(drift.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="columns"):
        load_factor_outcome_csv(_spec(drift, digest))


def test_artifact_date_and_currency_remain_canonical(tmp_path) -> None:
    path = tmp_path / "observations.csv"
    digest = _write(path, "run-a,AAA,2024-03-31,quality,quality_v1,70,12M,0.1,0.05,0.05,valid,SP500@2024,SPY,USD,quarterly\n")
    artifact = load_factor_outcome_csv(_spec(path, digest))
    assert artifact.observations[0].as_of == date(2024, 3, 31)
    assert artifact.observations[0].base_currency == "USD"


def test_verified_artifact_is_filtered_by_its_declared_manifest(tmp_path) -> None:
    path = tmp_path / "observations.csv"
    digest = _write(path, "run-a,AAA,2024-03-31,quality,quality_v1,70,12M,0.1,0.05,0.05,valid,SP500@2024,SPY,USD,quarterly\n")
    artifact = load_factor_outcome_csv(_spec(path, digest))
    manifest = StatisticalDatasetManifest(
        "dataset", "v1", datetime(2025, 1, 1, tzinfo=timezone.utc),
        DateWindow(date(2024, 1, 1), date(2024, 12, 31)), "USD",
        ("quality_v1",), ("SP500@2024",), ("SPY",), (artifact.snapshot_id,),
    )
    result = validate_artifact_manifest(artifact, manifest)
    assert result.valid
    assert result.selected_count == 1

    wrong_source = StatisticalDatasetManifest(
        "dataset", "v1", datetime(2025, 1, 1, tzinfo=timezone.utc),
        DateWindow(date(2024, 1, 1), date(2024, 12, 31)), "USD",
        ("quality_v1",), ("SP500@2024",), ("SPY",), ("other-snapshot",),
    )
    invalid = validate_artifact_manifest(artifact, wrong_source)
    assert not invalid.valid
    assert "snapshot" in " ".join(invalid.errors)
