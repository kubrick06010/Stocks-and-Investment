from datetime import date, datetime, timezone

from stocks_investment.domain import DataProvenance, MetricObservation, MetricStatus, Ticker
from stocks_investment.storage import SQLiteStorage


def test_sqlite_round_trip_and_point_in_time_filter(tmp_path) -> None:
    provenance = DataProvenance(
        source="fixture",
        provider="test",
        retrieved_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
        effective_date=date(2025, 1, 1),
        available_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
    )
    observation = MetricObservation(
        name="revenue",
        value=100.0,
        status=MetricStatus.VALID,
        as_of=date(2025, 1, 2),
        provenance=provenance,
    )
    with SQLiteStorage(tmp_path / "data.db") as storage:
        storage.save_observation(Ticker("aapl"), observation)
        assert storage.load_observations(Ticker("AAPL"), date(2025, 1, 1)) == ()
        loaded = storage.load_observations(Ticker("AAPL"), date(2025, 1, 3))
        assert loaded[0].value == 100.0


def test_raw_payload_is_content_addressed(tmp_path) -> None:
    retrieved = datetime(2025, 1, 2, tzinfo=timezone.utc)
    with SQLiteStorage(tmp_path / "data.db") as storage:
        first = storage.save_raw_payload(
            provider="test",
            endpoint="/fixture",
            parameters={"ticker": "AAPL"},
            payload="{}",
            retrieved_at=retrieved,
        )
        second = storage.save_raw_payload(
            provider="test",
            endpoint="/fixture",
            parameters={"ticker": "AAPL"},
            payload="{}",
            retrieved_at=retrieved,
        )
        assert first == second
