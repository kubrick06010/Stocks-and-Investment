from datetime import date, datetime, timezone

from stocks_investment.data.providers import FixtureProvider
from stocks_investment.domain import Period, ResearchResult, ResearchRun, ResearchRunStatus, Ticker
from stocks_investment.storage import SQLiteStorage


def test_foundation_vertical_slice_survives_reopen_and_as_of_filter(tmp_path) -> None:
    provider = FixtureProvider()
    ticker = Ticker("AAPL")
    period = Period(date(2025, 1, 1), date(2025, 3, 31), "quarter")
    observations = provider.metric_inputs(ticker, period, date(2025, 5, 3))
    assert observations[0].provenance.filing_date == date(2025, 5, 2)

    run = ResearchRun(
        id="run-fixture-001",
        created_at=datetime(2025, 5, 3, tzinfo=timezone.utc),
        as_of=date(2025, 5, 3),
        strategy_name="fixture_research",
        strategy_version="v1",
        universe_name="fixture",
        parameters={"source": "offline"},
        data_snapshot="fixture-v1",
        status=ResearchRunStatus.COMPLETED,
    )
    result = ResearchResult(
        id="result-fixture-001",
        run_id=run.id,
        ticker=ticker,
        created_at=run.created_at,
        rank=1,
        classification="RESEARCH",
    )

    path = tmp_path / "foundation.db"
    with SQLiteStorage(path) as storage:
        observation_id = storage.save_observation(ticker, observations[0])
        storage.save_research_run(run)
        storage.save_research_result(result)
        storage.attach_observation(result.id, observation_id)
        assert storage.load_observations(ticker, date(2025, 4, 30)) == ()

    with SQLiteStorage(path) as storage:
        assert storage.load_research_run(run.id) == run
        assert storage.load_research_result(result.id) == result
        linked = storage.load_result_observations(result.id, date(2025, 5, 3))
        assert linked[0].name == "revenue"
        assert linked[0].provenance.period_end == date(2025, 3, 31)
