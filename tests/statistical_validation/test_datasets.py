from datetime import date, datetime, timezone

from stocks_investment.domain import Ticker
from stocks_investment.domain.research_intelligence import FactorOutcomeObservation
from stocks_investment.domain.statistical_validation import (
    DateWindow,
    StatisticalDatasetManifest,
)
from stocks_investment.statistical_validation.datasets import (
    ExclusionReason,
    select_observations,
    validate_manifest,
)


def manifest() -> StatisticalDatasetManifest:
    return StatisticalDatasetManifest(
        id="quality-us-v1",
        version="1",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        window=DateWindow(date(2024, 1, 1), date(2024, 12, 31)),
        base_currency="USD",
        factor_versions=("quality_v1",),
        universe_versions=("SP500@2024",),
        benchmarks=("SP500",),
        source_snapshot_ids=("snapshot-1",),
    )


def observation(
    ticker: str,
    as_of: date,
    *,
    factor_version: str = "quality_v1",
    universe: str = "SP500@2024",
    benchmark: str = "SP500",
    currency: str = "USD",
    score: float | None = 80.0,
    security_return: float | None = 0.1,
    status: str = "measured",
    run_id: str | None = None,
) -> FactorOutcomeObservation:
    return FactorOutcomeObservation(
        factor_name="quality",
        factor_version=factor_version,
        research_run_id=run_id or f"run-{ticker}-{as_of}",
        ticker=Ticker(ticker),
        as_of=as_of,
        factor_score=score,
        horizon="12M",
        security_return=security_return,
        benchmark_return=0.05 if security_return is not None else None,
        excess_return=0.05 if security_return is not None else None,
        outcome_status=status,
        universe=universe,
        benchmark=benchmark,
        base_currency=currency,
        rebalance_cadence="quarterly",
    )


def test_selects_only_source_compatible_records_and_reports_reasons() -> None:
    records = (
        observation("BBB", date(2024, 3, 31)),
        observation("AAA", date(2024, 3, 31), factor_version="quality_v2"),
        observation("CCC", date(2025, 1, 1)),
        observation("DDD", date(2024, 3, 31), security_return=None),
        observation("EEE", date(2024, 3, 31), benchmark="NASDAQ"),
    )

    result = select_observations(manifest(), records)

    assert [item.ticker.symbol for item in result.observations] == ["BBB"]
    assert result.coverage == 0.2
    by_ticker = {item.observation.ticker.symbol: item.reasons for item in result.exclusions}
    assert ExclusionReason.FACTOR_VERSION in by_ticker["AAA"]
    assert ExclusionReason.OUT_OF_WINDOW in by_ticker["CCC"]
    assert ExclusionReason.MISSING_OUTCOME in by_ticker["DDD"]
    assert ExclusionReason.BENCHMARK in by_ticker["EEE"]


def test_selection_order_is_deterministic_and_does_not_mutate_input() -> None:
    records = [
        observation("ZZZ", date(2024, 6, 30), run_id="z"),
        observation("AAA", date(2024, 3, 31), run_id="a"),
        observation("BBB", date(2024, 3, 31), run_id="b"),
    ]
    original = tuple(records)

    first = select_observations(manifest(), records)
    second = select_observations(manifest(), records)

    assert first.observations == second.observations
    assert [item.ticker.symbol for item in first.observations] == ["AAA", "BBB", "ZZZ"]
    assert tuple(records) == original


def test_manifest_validation_reports_identity_and_coverage() -> None:
    result = validate_manifest(manifest(), (observation("AAA", date(2024, 1, 1)),))

    assert result.valid
    assert result.observation_count == 1
    assert result.selected_count == 1
    assert result.excluded_count == 0
    assert result.coverage == 1.0


def test_manifest_validation_rejects_duplicate_or_noncanonical_identity() -> None:
    invalid = StatisticalDatasetManifest(
        id="dataset",
        version="1",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        window=DateWindow(date(2024, 1, 1), date(2024, 12, 31)),
        base_currency="usd",
        factor_versions=("quality_v1", "quality_v1"),
        universe_versions=("SP500@2024",),
        benchmarks=("SP500",),
        source_snapshot_ids=("snapshot-1", "snapshot-1"),
    )

    result = validate_manifest(invalid)

    assert not result.valid
    assert "base currency must be uppercase" in result.errors
    assert "factor_versions must not contain duplicates" in result.errors
    assert "source_snapshot_ids must not contain duplicates" in result.errors
