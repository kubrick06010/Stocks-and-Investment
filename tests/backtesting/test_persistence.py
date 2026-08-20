from datetime import date, datetime, timezone

from stocks_investment.backtesting import BacktestConfigV1, BacktestPeriod, BacktestRun, SecurityAttribution, simulate_persisted_runs
from stocks_investment.domain import ResearchResult, ResearchRun, ResearchRunStatus, Ticker, UniverseSnapshot
from stocks_investment.storage import SQLiteStorage


def test_backtest_run_and_periods_survive_reopen(tmp_path) -> None:
    config = BacktestConfigV1(date(2025, 1, 1), date(2025, 2, 1), 1, 100, .01, "SYNTH")
    period = BacktestPeriod(0, "research-0", date(2025, 1, 1), date(2025, 1, 1), date(2025, 2, 1),
                            100, 109, .1, 1, 1, .09, .05, .04, ("AAA",),
                            (SecurityAttribution("AAA", 1, .1, .1),))
    run = BacktestRun("bt-0", "fixture", "fixture-v1", config, (period,), 109)
    path = tmp_path / "backtest.db"
    with SQLiteStorage(path) as storage:
        storage.save_backtest_run(run)
    with SQLiteStorage(path) as storage:
        loaded = storage.load_backtest_run("bt-0")
    assert loaded == run


def test_backtest_consumes_reopened_research_runs(tmp_path) -> None:
    t0, t1, end = date(2025, 1, 1), date(2025, 2, 1), date(2025, 3, 1)
    run0 = ResearchRun("research-0", datetime(2025, 1, 1, tzinfo=timezone.utc), t0, "fixture", "fixture-v1", "synthetic", "u0", t0, {}, status=ResearchRunStatus.COMPLETED)
    run1 = ResearchRun("research-1", datetime(2025, 2, 1, tzinfo=timezone.utc), t1, "fixture", "fixture-v1", "synthetic", "u1", t1, {}, status=ResearchRunStatus.COMPLETED)
    u0 = UniverseSnapshot("synthetic", "u0", t0, (Ticker("AAA"),), "fixture")
    u1 = UniverseSnapshot("synthetic", "u1", t1, (Ticker("AAA"),), "fixture")
    r0 = ResearchResult("research-0:AAA", run0.id, Ticker("AAA"), run0.created_at, 1, 90, "selected")
    r1 = ResearchResult("research-1:AAA", run1.id, Ticker("AAA"), run1.created_at, 1, 91, "selected")
    path = tmp_path / "lineage.db"
    with SQLiteStorage(path) as storage:
        for universe, run, result in ((u0, run0, r0), (u1, run1, r1)):
            storage.save_universe_snapshot(universe)
            storage.save_research_run(run)
            storage.save_research_result(result)
    with SQLiteStorage(path) as storage:
        reopened = ((storage.load_research_run(run0.id), (storage.load_research_result(r0.id),)),
                    (storage.load_research_run(run1.id), (storage.load_research_result(r1.id),)))
        assert all(run is not None and result[0] is not None for run, result in reopened)
        backtest = simulate_persisted_runs(
            tuple((run, result) for run, result in reopened if run is not None and result[0] is not None
                  for result in ((result[0],),)),
            {t0: {"AAA": 100}, t1: {"AAA": 110}, end: {"AAA": 121}},
            {t0: 100, t1: 100, end: 100},
            config=BacktestConfigV1(t0, end, 1, 100, .01, "SYNTH"),
            universes={("synthetic", "u0"): u0, ("synthetic", "u1"): u1},
        )
        assert tuple(period.research_run_id for period in backtest.periods) == ("research-0", "research-1")
