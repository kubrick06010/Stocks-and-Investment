from datetime import date, datetime, timezone

from pytest import approx, raises

from stocks_investment.backtesting import BacktestConfigV1, simulate_persisted_runs
from stocks_investment.domain import ResearchResult, ResearchRun, ResearchRunStatus, Ticker


def _run(identifier: str, when: date) -> ResearchRun:
    return ResearchRun(identifier, datetime.combine(when, datetime.min.time(), timezone.utc), when,
                       "fixture", "fixture_v1", "synthetic", f"synthetic_{when}", when,
                       {}, status=ResearchRunStatus.COMPLETED)


def _result(run: ResearchRun, symbol: str, rank: int) -> ResearchResult:
    return ResearchResult(f"{run.id}:{symbol}", run.id, Ticker(symbol), run.created_at, rank, float(100 - rank), "selected")


def test_multi_period_rebalance_turnover_cost_and_compounding() -> None:
    t0, t1, t2, end = (date(2025, 1, 1), date(2025, 2, 1), date(2025, 3, 1), date(2025, 4, 1))
    r0, r1, r2 = _run("r0", t0), _run("r1", t1), _run("r2", t2)
    runs = ((r0, (_result(r0, "AAA", 1), _result(r0, "BBB", 2))),
            (r1, (_result(r1, "AAA", 1), _result(r1, "CCC", 2))),
            (r2, (_result(r2, "CCC", 1), _result(r2, "DDD", 2))))
    prices = {
        t0: {"AAA": 100, "BBB": 100}, t1: {"AAA": 110, "BBB": 90, "CCC": 50},
        t2: {"AAA": 110, "CCC": 60, "DDD": 100}, end: {"AAA": 110, "CCC": 66, "DDD": 110},
    }
    result = simulate_persisted_runs(runs, prices, {t0: 100, t1: 100, t2: 100, end: 100},
                                     config=BacktestConfigV1(t0, end, 2, 1000, .01, "SYNTH"))
    assert result.periods[0].research_run_id == "r0"
    assert result.periods[1].research_run_id == "r1"
    assert result.periods[1].turnover > 0
    assert result.periods[1].transaction_cost > 0
    assert result.final_value == approx(result.periods[-1].ending_value)
    assert result.total_return == approx(result.final_value / 1000 - 1)
    compounded = 1000
    for period in result.periods:
        compounded *= 1 + period.net_return
    assert result.final_value == approx(compounded)


def test_zero_turnover_has_zero_cost() -> None:
    t0, t1, end = date(2025, 1, 1), date(2025, 2, 1), date(2025, 3, 1)
    r0, r1 = _run("r0", t0), _run("r1", t1)
    runs = ((r0, (_result(r0, "AAA", 1), _result(r0, "BBB", 2))),
            (r1, (_result(r1, "AAA", 1), _result(r1, "BBB", 2))))
    prices = {t0: {"AAA": 100, "BBB": 100}, t1: {"AAA": 100, "BBB": 100}, end: {"AAA": 100, "BBB": 100}}
    result = simulate_persisted_runs(runs, prices, {}, config=BacktestConfigV1(t0, end, 2, 100, .05, "SYNTH"))
    assert result.periods[1].turnover == 0
    assert result.periods[1].transaction_cost == 0


def test_missing_selected_price_fails_explicitly() -> None:
    t0, end = date(2025, 1, 1), date(2025, 2, 1)
    run = _run("r0", t0)
    with raises(ValueError, match="missing price"):
        simulate_persisted_runs(((run, (_result(run, "AAA", 1),)),), {t0: {"AAA": 1}, end: {}}, {}, config=BacktestConfigV1(t0, end, 1, 100, .01, "SYNTH"))
