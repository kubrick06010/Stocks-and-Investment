"""Offline ingestion of hash-pinned historical factor/outcome artifacts.

This boundary deliberately does not download data or infer accounting facts.
An operator supplies an already acquired artifact plus its license and source
identity.  The loader only normalizes the documented CSV representation into
canonical persisted-observation inputs.
"""

from __future__ import annotations

import csv
import hashlib
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from stocks_investment.domain import FactorOutcomeObservation, Ticker
from stocks_investment.domain.statistical_validation import StatisticalDatasetManifest
from stocks_investment.statistical_validation.datasets import ManifestValidation, validate_manifest


@dataclass(frozen=True, slots=True)
class DatasetArtifactSpec:
    path: Path
    sha256: str
    license_id: str
    source_uri: str
    snapshot_id: str

    def __post_init__(self) -> None:
        if not self.sha256 or len(self.sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.sha256.lower()
        ):
            raise ValueError("artifact sha256 must be a 64-character hexadecimal digest")
        if not self.license_id.strip() or not self.source_uri.strip() or not self.snapshot_id.strip():
            raise ValueError("artifact license, source URI and snapshot identity are required")


@dataclass(frozen=True, slots=True)
class DatasetArtifact:
    observations: tuple[FactorOutcomeObservation, ...]
    sha256: str
    source_uri: str
    license_id: str
    snapshot_id: str


def validate_artifact_manifest(
    artifact: DatasetArtifact,
    manifest: StatisticalDatasetManifest,
) -> ManifestValidation:
    """Apply the canonical cohort boundary to one verified source artifact."""

    validation = validate_manifest(manifest, artifact.observations)
    errors = list(validation.errors)
    if artifact.snapshot_id not in manifest.source_snapshot_ids:
        errors.append("artifact snapshot is not named by the dataset manifest")
    if errors == list(validation.errors):
        return validation
    return ManifestValidation(
        valid=False,
        errors=tuple(errors),
        observation_count=validation.observation_count,
        selected_count=validation.selected_count,
        excluded_count=validation.excluded_count,
        coverage=validation.coverage,
    )


_COLUMNS = (
    "research_run_id", "ticker", "as_of", "factor_name", "factor_version",
    "factor_score", "horizon", "security_return", "benchmark_return",
    "excess_return", "outcome_status", "universe", "benchmark", "base_currency",
    "rebalance_cadence",
)


def load_factor_outcome_csv(spec: DatasetArtifactSpec) -> DatasetArtifact:
    """Load a hash-pinned CSV without network access or silent coercion."""

    content = spec.path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if digest != spec.sha256.lower():
        raise ValueError("artifact sha256 does not match the supplied digest")

    rows: list[FactorOutcomeObservation] = []
    seen: set[tuple[object, ...]] = set()
    with spec.path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or tuple(reader.fieldnames) != _COLUMNS:
            raise ValueError("artifact CSV columns do not match the canonical schema")
        for line_number, row in enumerate(reader, start=2):
            if None in row or any(row.get(column) is None for column in _COLUMNS):
                raise ValueError(f"artifact row {line_number} has missing columns")
            observation = _observation_from_row(row, line_number)
            identity = (
                observation.research_run_id, observation.ticker.symbol, observation.as_of,
                observation.factor_name, observation.factor_version, observation.horizon,
                observation.universe, observation.benchmark, observation.base_currency,
                observation.rebalance_cadence,
            )
            if identity in seen:
                raise ValueError(f"artifact contains duplicate observation identity at row {line_number}")
            seen.add(identity)
            rows.append(observation)

    rows.sort(key=_observation_key)
    return DatasetArtifact(tuple(rows), digest, spec.source_uri, spec.license_id, spec.snapshot_id)


def _observation_from_row(row: dict[str, str], line_number: int) -> FactorOutcomeObservation:
    try:
        return FactorOutcomeObservation(
            row["factor_name"], row["factor_version"], row["research_run_id"],
            Ticker(row["ticker"]), date.fromisoformat(row["as_of"]),
            _number(row["factor_score"], "factor_score", line_number), row["horizon"],
            _number(row["security_return"], "security_return", line_number),
            _number(row["benchmark_return"], "benchmark_return", line_number),
            _number(row["excess_return"], "excess_return", line_number),
            row["outcome_status"], row["universe"], row["benchmark"],
            row["base_currency"], row["rebalance_cadence"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"invalid artifact row {line_number}: {error}") from error


def _number(value: str, field: str, line_number: int) -> float | None:
    if value == "":
        return None
    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError(f"{field} is not numeric at row {line_number}") from error
    if not math.isfinite(parsed):
        raise ValueError(f"{field} must be finite at row {line_number}")
    return parsed


def _observation_key(observation: FactorOutcomeObservation) -> tuple[object, ...]:
    return (
        observation.as_of, observation.ticker.symbol, observation.factor_name,
        observation.factor_version, observation.horizon, observation.research_run_id,
    )
