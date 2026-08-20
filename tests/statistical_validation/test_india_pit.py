from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from stocks_investment.domain.statistical_validation import DateWindow, StatisticalDatasetManifest
from stocks_investment.statistical_validation.datasets import ExclusionReason, select_observations
from stocks_investment.statistical_validation.india_pit import (
    BENCHMARK_VERSION,
    FACTOR_VERSION,
    UNIVERSE_VERSION,
    IndiaPitBundleSpec,
    build_india_pit_observations,
)
from stocks_investment.statistical_validation import india_pit_validation
from stocks_investment.statistical_validation.india_pit_validation import (
    load_bundle_spec,
    run_india_pit_validation,
)
from stocks_investment.statistical_validation.artifacts import DatasetArtifactSpec
from stocks_investment.storage import SQLiteStorage


_UNIVERSE_HEADER = (
    "symbol,first_traded,last_traded,n_days,isin,continuity_id,company_name,"
    "listing_date,status\n"
)
_PRICE_HEADER = "date,symbol,isin,adj_close,tr_close,deliv_pct\n"
_FUNDAMENTAL_HEADER = (
    "symbol,period_end,announce_date,consolidated,revenue_cr,pat_cr,eps_basic,"
    "total_income_cr,announce_lag_days\n"
)


def _bundle(tmp_path: Path, *, extra_price: str = "") -> IndiaPitBundleSpec:
    files = {
        "survivorship_universe.csv": (
            _UNIVERSE_HEADER
            + "AAA,2020-01-01,2022-12-31,700,INAAA,AAA,Alpha,2020-01-01,active\n"
            + "BBB,2020-01-01,2021-05-31,350,INBBB,BBB,Beta,2020-01-01,inactive\n"
            + "CCC,2020-01-01,2022-12-31,700,INCCC,CCC,Gamma,2020-01-01,active\n"
        ).encode(),
        "prices_sample.csv": (
            _PRICE_HEADER
            + "2021-06-30,AAA,INAAA,110,110,\n"
            + "2021-03-31,AAA,INAAA,100,100,\n"
            + "2021-05-31,BBB,INBBB,25,25,\n"
            + "2021-03-31,BBB,INBBB,50,50,\n"
            + "2021-03-31,CCC,INCCC,100,100,\n"
            + extra_price
        ).encode(),
        "fundamentals_sample.csv": (
            _FUNDAMENTAL_HEADER
            + "AAA,2020-12-31,2021-02-15,true,100,10,1,100,46\n"
            + "AAA,2021-03-31,2021-05-01,true,100,20,2,100,31\n"
            + "BBB,2020-12-31,2021-02-10,true,100,5,1,100,41\n"
            + "CCC,2020-12-31,2021-02-05,true,100,0,0,100,36\n"
        ).encode(),
    }
    path = tmp_path / "india-pit.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, payload in reversed(tuple(files.items())):
            bundle.writestr(name, payload)
    artifact = DatasetArtifactSpec(
        path,
        hashlib.sha256(path.read_bytes()).hexdigest(),
        "CC-BY-4.0",
        "https://www.kaggle.com/datasets/financebroski/"
        "survivorship-free-indian-equity-data-nsebse",
        "financebroski-india-pit-sample-kaggle-v3",
    )
    return IndiaPitBundleSpec(
        artifact,
        {name: hashlib.sha256(payload).hexdigest() for name, payload in files.items()},
    )


def test_pit_factor_and_returns_preserve_identity_and_future_filing_barrier(
    tmp_path: Path,
) -> None:
    result = build_india_pit_observations(
        _bundle(tmp_path), research_dates=(date(2021, 3, 31),), horizons=("3M",)
    )

    by_symbol = {item.ticker.symbol: item for item in result.observations}
    assert tuple(by_symbol) == ("AAA", "BBB", "CCC")
    assert by_symbol["AAA"].factor_score == 100.0
    assert by_symbol["BBB"].factor_score == 50.0
    assert by_symbol["CCC"].factor_score == 0.0
    assert by_symbol["AAA"].security_return == pytest.approx(0.10)
    assert by_symbol["BBB"].security_return == pytest.approx(-0.50)
    assert by_symbol["CCC"].security_return is None
    assert by_symbol["AAA"].benchmark_return == pytest.approx(-0.20)
    assert by_symbol["AAA"].excess_return == pytest.approx(0.30)
    assert by_symbol["BBB"].outcome_status == "measured_terminal_cash_approximation"
    assert by_symbol["CCC"].outcome_status == "unavailable"
    assert result.terminal_cash_approximations == 1
    assert result.unavailable_outcomes == 1


def test_terminal_approximation_and_missing_outcomes_are_not_validation_evidence(
    tmp_path: Path,
) -> None:
    result = build_india_pit_observations(
        _bundle(tmp_path), research_dates=(date(2021, 3, 31),), horizons=("3M",)
    )
    manifest = StatisticalDatasetManifest(
        "india-sample",
        "dataset_manifest_v1",
        datetime(2021, 7, 1, tzinfo=timezone.utc),
        DateWindow(date(2021, 3, 31), date(2021, 3, 31)),
        "INR",
        (FACTOR_VERSION,),
        (UNIVERSE_VERSION,),
        (BENCHMARK_VERSION,),
        (result.source_sha256,),
    )

    selection = select_observations(manifest, result.observations)

    assert tuple(item.ticker.symbol for item in selection.observations) == ("AAA",)
    reasons = {
        item.observation.ticker.symbol: item.reasons for item in selection.exclusions
    }
    assert ExclusionReason.INVALID_OUTCOME_STATUS in reasons["BBB"]
    assert ExclusionReason.MISSING_OUTCOME in reasons["CCC"]


def test_hashes_schema_and_unknown_symbols_fail_closed(tmp_path: Path) -> None:
    spec = _bundle(tmp_path)
    wrong_archive = IndiaPitBundleSpec(
        DatasetArtifactSpec(
            spec.artifact.path,
            "0" * 64,
            spec.artifact.license_id,
            spec.artifact.source_uri,
            spec.artifact.snapshot_id,
        ),
        spec.inner_sha256,
    )
    with pytest.raises(ValueError, match="bundle SHA-256"):
        build_india_pit_observations(
            wrong_archive, research_dates=(date(2021, 3, 31),), horizons=("3M",)
        )

    wrong_inner = IndiaPitBundleSpec(
        spec.artifact,
        {**spec.inner_sha256, "prices_sample.csv": "0" * 64},
    )
    with pytest.raises(ValueError, match="inner SHA-256"):
        build_india_pit_observations(
            wrong_inner, research_dates=(date(2021, 3, 31),), horizons=("3M",)
        )

    unknown = _bundle(tmp_path, extra_price="2021-03-31,ZZZ,INZZZ,10,10,\n")
    with pytest.raises(ValueError, match="outside the universe"):
        build_india_pit_observations(
            unknown, research_dates=(date(2021, 3, 31),), horizons=("3M",)
        )


def test_configuration_and_bundle_contract_reject_ambiguous_inputs(tmp_path: Path) -> None:
    spec = _bundle(tmp_path)
    with pytest.raises(ValueError, match="research dates"):
        build_india_pit_observations(
            spec,
            research_dates=(date(2021, 6, 30), date(2021, 3, 31)),
            horizons=("3M",),
        )
    with pytest.raises(ValueError, match="unique"):
        build_india_pit_observations(
            spec, research_dates=(date(2021, 3, 31),), horizons=("3M", "3M")
        )
    with pytest.raises(ValueError, match="unsupported"):
        build_india_pit_observations(
            spec, research_dates=(date(2021, 3, 31),), horizons=("9M",)
        )
    with pytest.raises(ValueError, match="all three"):
        IndiaPitBundleSpec(spec.artifact, {"prices_sample.csv": "0" * 64})


def test_real_data_boundary_persists_and_reopens_without_provider_access(
    tmp_path: Path,
) -> None:
    result = build_india_pit_observations(
        _bundle(tmp_path), research_dates=(date(2021, 3, 31),), horizons=("3M",)
    )
    database = tmp_path / "india-pit.db"
    with SQLiteStorage(database) as storage:
        for observation in result.observations:
            storage.save_factor_outcome_observation(observation)

    with SQLiteStorage(database) as reopened:
        persisted = reopened.load_factor_outcome_observations(
            factor_name="profitability_margin", factor_version=FACTOR_VERSION
        )

    assert persisted == result.observations


def test_bounded_validation_runner_is_reproducible_and_never_claims_efficacy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _bundle(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "artifact_sha256": spec.artifact.sha256,
                "files": {
                    name: {"sha256": digest}
                    for name, digest in spec.inner_sha256.items()
                },
                "license": spec.artifact.license_id,
                "source_uri": spec.artifact.source_uri,
                "snapshot_id": spec.artifact.snapshot_id,
            }
        ),
        encoding="utf-8",
    )
    loaded = load_bundle_spec(manifest_path, spec.artifact.path)
    monkeypatch.setattr(
        india_pit_validation,
        "RESEARCH_DATES",
        (date(2021, 3, 31),),
    )
    output = tmp_path / "derived"

    report = run_india_pit_validation(loaded, output_directory=output)

    assert report["verdict"] == "NO_GO_ECONOMIC_VALIDATION"
    assert report["persistence"]["close_reopen_verified"] is True
    assert report["persistence"]["provider_calls"] == 0
    assert (output / "india-pit-validation-v1.sqlite3").is_file()
    assert (output / "india-pit-validation-v1.json").is_file()
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        run_india_pit_validation(loaded, output_directory=output)
