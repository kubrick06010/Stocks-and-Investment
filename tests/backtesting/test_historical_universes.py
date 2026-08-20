from datetime import date, datetime, timezone

from pytest import raises

from stocks_investment.backtesting import BacktestConfigV1, simulate_persisted_runs
from stocks_investment.domain import ResearchResult, ResearchRun, ResearchRunStatus, Ticker, UniverseSnapshot


def _run(identifier: str, when: date, version: str) -> ResearchRun:
    return ResearchRun(identifier, datetime.combine(when, datetime.min.time(), timezone.utc), when,
                       "balanced_fixture", "balanced_fixture_v1", "synthetic", version, when,
                       {}, status=ResearchRunStatus.COMPLETED)


def _results(run: ResearchRun, symbols: tuple[str, ...]) -> tuple[ResearchResult, ...]:
    return tuple(ResearchResult(f"{run.id}:{symbol}", run.id, Ticker(symbol), run.created_at, i + 1, 100 - i, "selected")
                 for i, symbol in enumerate(symbols))


def test_three_historical_universes_exclude_future_members_and_are_reproducible() -> None:
    t0, t1, t2, end = date(2025, 1, 1), date(2025, 4, 1), date(2025, 7, 1), date(2025, 10, 1)
    r0, r1, r2 = _run("r0", t0, "u0"), _run("r1", t1, "u1"), _run("r2", t2, "u2")
    universes = {
        ("synthetic", "u0"): UniverseSnapshot("synthetic", "u0", t0, tuple(Ticker(x) for x in ("AAA", "BBB", "CCC", "DDD")), "fixture"),
        ("synthetic", "u1"): UniverseSnapshot("synthetic", "u1", t1, tuple(Ticker(x) for x in ("AAA", "BBB", "DDD", "EEE")), "fixture"),
        ("synthetic", "u2"): UniverseSnapshot("synthetic", "u2", t2, tuple(Ticker(x) for x in ("AAA", "DDD", "EEE", "FFF")), "fixture"),
    }
    runs = ((r0, _results(r0, ("AAA", "BBB"))), (r1, _results(r1, ("AAA", "EEE"))), (r2, _results(r2, ("FFF", "AAA"))))
    prices = {when: {symbol: 100.0 for symbol in ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF")} for when in (t0, t1, t2, end)}
    config = BacktestConfigV1(t0, end, 2, 1000, .001, "SYNTH")
    first = simulate_persisted_runs(runs, prices, {when: 100 for when in prices}, config=config, universes=universes)
    second = simulate_persisted_runs(runs, prices, {when: 100 for when in prices}, config=config, universes=universes)
    assert first.periods[0].selected_symbols == ("AAA", "BBB")
    assert first.periods[1].selected_symbols == ("AAA", "EEE")
    assert first.periods[2].selected_symbols == ("FFF", "AAA")
    assert first == second
    assert "EEE" not in universes[("synthetic", "u0")].members
    assert "FFF" not in universes[("synthetic", "u0")].members


def test_result_outside_historical_universe_is_rejected_even_if_price_exists() -> None:
    t0, end = date(2025, 1, 1), date(2025, 2, 1)
    run = _run("r0", t0, "u0")
    universe = UniverseSnapshot("synthetic", "u0", t0, (Ticker("AAA"),), "fixture")
    result = _results(run, ("EEE",))
    with raises(ValueError, match="outside its historical universe"):
        simulate_persisted_runs(((run, result),), {t0: {"EEE": 100}, end: {"EEE": 100}}, {},
                                config=BacktestConfigV1(t0, end, 1, 100, .01, "SYNTH"),
                                universes={("synthetic", "u0"): universe})
