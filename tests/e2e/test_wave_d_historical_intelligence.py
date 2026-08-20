from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest

from stocks_investment.comparison import compare_rankings
from stocks_investment.comparison import compare_backtests
from stocks_investment.cli import main as cli_main
from stocks_investment.backtesting import BacktestConfigV1, CorporateActionMode, simulate_persisted_runs
from stocks_investment.domain import (
    AnalysisStatus,
    CriterionResult,
    CriterionStatus,
    FactorObservation,
    FactorScore,
    ResearchOutcome,
    ResearchResult,
    ResearchRun,
    ResearchRunStatus,
    Ticker,
    UniverseSnapshot,
    WatchCondition,
    WatchlistEntry,
    WatchlistStatus,
)
from stocks_investment.domain.research_intelligence import (
    CohortIdentity,
    FactorOutcomeObservation,
    MaterialityPolicy,
    MaterialityRule,
    MaterialityRuleType,
    ReportSection,
    SourceReference,
    ThesisClassification,
    ThesisSnapshot,
)
from stocks_investment.factor_research import summarize_factor
from stocks_investment.history import compare_results
from stocks_investment.reporting import build_report, render_json, render_markdown
from stocks_investment.storage import SQLiteStorage
from stocks_investment.thesis import StructuredThesisEngine
from stocks_investment.watchlist import evaluate_watchlist


DATES = (date(2024, 3, 31), date(2024, 6, 30), date(2024, 9, 30), date(2024, 12, 31))
SYMBOLS = ("AAA", "BBB", "CCC", "DDD", "EEE")


def _run(run_id: str, as_of: date, strategy: str = "balanced_value_quality") -> ResearchRun:
    return ResearchRun(
        run_id,
        datetime.combine(as_of, datetime.min.time(), tzinfo=timezone.utc),
        as_of,
        strategy,
        f"{strategy}_v1",
        "synthetic",
        f"synthetic@{as_of.isoformat()}",
        as_of,
        {"top_n": 2, "fixture": "wave_d"},
        data_snapshot="wave_d_fixture_v1",
        status=ResearchRunStatus.COMPLETED,
    )


def _factor(name: str, score: float, run: ResearchRun) -> FactorScore:
    observation = FactorObservation(
        name,
        score,
        AnalysisStatus.VALID,
        "score",
        run.as_of,
        "TTM",
        f"{name}_v1",
        source_metric=name,
    )
    return FactorScore(name, f"{name}_v1", score, AnalysisStatus.VALID, 1.0, (observation,), f"{name} fixture score")


def _result(run: ResearchRun, symbol: str, rank: int, value: float, quality: float, pe: float) -> ResearchResult:
    pe_criterion = CriterionResult(
        "pe_ttm", "pe_ttm_v1", pe, 18.0,
        CriterionStatus.PASS if pe <= 18 else CriterionStatus.FAIL,
        pe <= 18,
        "P/E is at or below the fixture threshold" if pe <= 18 else "P/E remains above the fixture threshold",
    )
    graham_pass = value >= 70 and quality >= 80
    graham = CriterionResult(
        "graham_defensive", "graham_defensive_v1", 1 if graham_pass else 0, 1,
        CriterionStatus.PASS if graham_pass else CriterionStatus.FAIL,
        graham_pass,
        "value and quality criteria pass" if graham_pass else "one or more Graham criteria fail",
    )
    factors = (_factor("value", value, run), _factor("quality", quality, run))
    composite = round((value + quality) / 2, 2)
    return ResearchResult(
        f"{run.id}:{symbol}", run.id, Ticker(symbol), run.created_at, rank, composite,
        "selected" if rank <= 2 else "watch", factors, (pe_criterion, graham),
    )


def _persist_story(storage: SQLiteStorage) -> dict[str, tuple[ResearchRun, tuple[ResearchResult, ...]]]:
    story: dict[str, tuple[ResearchRun, tuple[ResearchResult, ...]]] = {}
    values = {
        "AAA": ((48, 92, 26), (57, 92, 23), (72, 93, 19), (77, 93, 17)),
        "BBB": ((35, 96, 31), (38, 96, 30), (42, 97, 29), (45, 97, 28)),
        "CCC": ((90, 35, 8), (88, 34, 7), (86, 32, 6), (84, 30, 5)),
        "DDD": ((76, 92, 14), (70, 84, 15), (58, 70, 17), (48, 61, 20)),
        "EEE": ((60, 65, 22), (65, 70, 20), (70, 76, 18), (75, 82, 16)),
    }
    ranks = {
        0: (2, 3, 1, 4, 5), 1: (2, 4, 3, 1, 5), 2: (1, 4, 5, 3, 2), 3: (1, 4, 5, 3, 2)
    }
    for index, as_of in enumerate(DATES):
        run = _run(f"run-{index}", as_of)
        members = tuple(Ticker(symbol) for symbol in SYMBOLS)
        storage.save_universe_snapshot(UniverseSnapshot("synthetic", f"synthetic@{as_of.isoformat()}", as_of, members, "fixture"))
        results = tuple(
            _result(run, symbol, ranks[index][position], *values[symbol][index])
            for position, symbol in enumerate(SYMBOLS)
        )
        storage.save_research_run(run)
        for result in results:
            storage.save_research_result(result)
            outcome = ResearchOutcome(result.id, date(2025, 3, 31), "12M", 0.08 if result.ticker.symbol in {"AAA", "EEE"} else -0.02, 0.03, 0.05 if result.ticker.symbol in {"AAA", "EEE"} else -0.05)
            storage.save_research_outcome(outcome)
            for factor in result.factor_scores:
                storage.save_factor_outcome_observation(FactorOutcomeObservation(
                    factor.factor_name, factor.factor_version, run.id, result.ticker, run.as_of,
                    factor.score, outcome.horizon, outcome.forward_return, outcome.benchmark_return,
                    outcome.excess_return, "valid", "synthetic", "fixture", "USD", "quarterly",
                ))
        story[run.id] = (run, results)
    return story


def test_wave_d_four_run_story_survives_reopen_and_future_attack(tmp_path) -> None:
    db_path = tmp_path / "wave-d.sqlite"
    storage = SQLiteStorage(db_path)
    story = _persist_story(storage)
    thesis_engine = StructuredThesisEngine()
    snapshots: dict[str, ThesisSnapshot] = {}
    for run, results in story.values():
        for result in results:
            snapshot = thesis_engine.generate(run, result)
            storage.save_thesis_snapshot(snapshot)
            snapshots[snapshot.id] = snapshot
    aaa_t0 = snapshots["thesis:run-0:AAA:structured_thesis_v1"]
    aaa_t3 = snapshots["thesis:run-3:AAA:structured_thesis_v1"]
    assert aaa_t0.classification is ThesisClassification.WATCH
    assert aaa_t3.classification is ThesisClassification.ATTRACTIVE
    ddd_t3 = snapshots["thesis:run-3:DDD:structured_thesis_v1"]
    assert ddd_t3.classification is ThesisClassification.DETERIORATING

    policy = MaterialityPolicy("wave_d_policy_v1", (
        MaterialityRule("rank", MaterialityRuleType.RANK_MOVEMENT, 1, "rank_v1"),
        MaterialityRule("classification", MaterialityRuleType.STATUS_TRANSITION, None, "class_v1"),
        MaterialityRule("composite_score", MaterialityRuleType.ABSOLUTE, 5, "score_v1"),
        MaterialityRule("factor:quality", MaterialityRuleType.ABSOLUTE, 5, "factor_v1"),
    ))
    for index in range(3):
        old_run, old_results = story[f"run-{index}"]
        new_run, new_results = story[f"run-{index + 1}"]
        for symbol in ("AAA", "DDD"):
            old = next(item for item in old_results if item.ticker.symbol == symbol)
            new = next(item for item in new_results if item.ticker.symbol == symbol)
            for event in compare_results(old_run, old, new_run, new, policy):
                storage.save_change_event(event)
    assert storage.load_change_events(Ticker("AAA"))
    assert any(event.change_type.value == "classification_change" for event in storage.load_change_events(Ticker("DDD")))

    entry = WatchlistEntry(
        "watch-aaa", Ticker("AAA"), story["run-0"][0].created_at, "run-0", "run-0:AAA",
        "High quality, valuation initially too demanding", WatchlistStatus.ACTIVE,
        target_conditions=(WatchCondition("pe_ttm", "<=", 18, "watch_pe_v1"), WatchCondition("classification", "==", "attractive", "watch_class_v1")),
    )
    storage.save_watchlist_entry(entry)
    previous: dict[str, object] = {}
    for run_id in ("run-0", "run-1", "run-2", "run-3"):
        run, results = story[run_id]
        result = next(item for item in results if item.ticker.symbol == "AAA")
        events = evaluate_watchlist(entry, run, result, previous)
        for event in events:
            storage.save_monitoring_event(event)
        previous = {"pe_ttm": next(item for item in result.criteria if item.criterion_name == "pe_ttm").observed, "classification": result.classification}
    assert any(event.triggered for event in storage.load_monitoring_events(entry.id))
    before = len(storage.load_monitoring_events(entry.id))
    run, results = story["run-3"]
    assert evaluate_watchlist(entry, run, next(item for item in results if item.ticker.symbol == "AAA"), previous) == ()
    assert len(storage.load_monitoring_events(entry.id)) == before

    # D3 consumes persisted run/result pairs and retains strategy identity.
    balanced = story["run-2"]
    alternate_run = _run("graham-run-2", DATES[2], "graham_defensive")
    alternate = tuple(sorted(balanced[1], key=lambda result: (result.ticker.symbol == "CCC", result.rank or 0)))
    alternate = tuple(result.__class__(result.id + ":g", alternate_run.id, result.ticker, alternate_run.created_at, index + 1, result.composite_score, result.classification, result.factor_scores, result.criteria) for index, result in enumerate(alternate))
    comparison = compare_rankings((balanced[0], balanced[1]), (alternate_run, alternate), top_n=2)
    assert comparison.strategy_a != comparison.strategy_b
    assert comparison.metadata["jaccard"] is not None
    incompatible = compare_rankings((balanced[0], balanced[1]), (_run("other", DATES[1], "balanced_value_quality"), alternate), top_n=2)
    assert "as_of" in incompatible.assumption_mismatches

    # D4 is built from data read back from persistence, never recomputed scores.
    efficacy_inputs = []
    for result in balanced[1]:
        quality = next(item for item in result.factor_scores if item.factor_name == "quality")
        outcome = storage.load_research_outcomes(result.id)[0]
        efficacy_inputs.append(FactorOutcomeObservation("quality", quality.factor_version, result.run_id, result.ticker, balanced[0].as_of, quality.score, outcome.horizon, outcome.forward_return, outcome.benchmark_return, outcome.excess_return, "valid", "synthetic", "fixture", "USD", "quarterly"))
    cohort = CohortIdentity("quality_v1", "synthetic", balanced[0].as_of, balanced[0].as_of, "12M", "quarterly", "USD", "fixture")
    efficacy = summarize_factor(tuple(efficacy_inputs), cohort)
    assert efficacy.sample_size == 5 and efficacy.coverage == 1
    with pytest.raises(ValueError, match="cohort"):
        summarize_factor(tuple(efficacy_inputs) + (efficacy_inputs[0].__class__("quality", "quality_v2", "other", Ticker("AAA"), balanced[0].as_of, 90, "12M", .1, .02, .08, "valid", "synthetic", "fixture", "USD", "quarterly"),), cohort)

    prices = {
        DATES[0]: {symbol: 100.0 for symbol in SYMBOLS},
        DATES[1]: {symbol: 102.0 for symbol in SYMBOLS},
        DATES[2]: {symbol: 104.0 for symbol in SYMBOLS},
        DATES[3]: {symbol: 108.0 for symbol in SYMBOLS},
        date(2025, 3, 31): {symbol: 110.0 for symbol in SYMBOLS},
    }
    benchmark_prices = {when: 100.0 + index for index, when in enumerate(prices)}
    config = BacktestConfigV1(DATES[0], date(2025, 3, 31), 2, 1000.0, .01, "FIXTURE_BENCHMARK", CorporateActionMode.RAW_PRICES_EXPLICIT_ACTIONS)
    persisted_balanced = simulate_persisted_runs(tuple(story.values()), prices, benchmark_prices, config=config)
    graham_runs = []
    for index, as_of in enumerate(DATES):
        balanced_run, results = story[f"run-{index}"]
        graham_run = _run(f"graham-{index}", as_of, "graham_defensive")
        graham_results = tuple(result.__class__(f"{graham_run.id}:{result.ticker.symbol}", graham_run.id, result.ticker, graham_run.created_at, result.rank, result.composite_score, result.classification, result.factor_scores, result.criteria) for result in results)
        storage.save_research_run(graham_run)
        for result in graham_results:
            storage.save_research_result(result)
        graham_runs.append((graham_run, graham_results))
    persisted_graham = simulate_persisted_runs(tuple(graham_runs), prices, benchmark_prices, config=config)
    storage.save_backtest_run(persisted_balanced)
    storage.save_backtest_run(persisted_graham)
    performance_comparison = compare_backtests(persisted_graham, persisted_balanced)
    assert performance_comparison.metadata["compatible"] is True
    assert performance_comparison.metadata["performance_a"]["transaction_costs"] >= 0

    report = build_report("single_stock", DATES[3], ("run-0", "run-3"), ())
    assert "run-0" in render_json(report)
    assert "# single_stock" in render_markdown(report)
    storage.close()

    reopened = SQLiteStorage(db_path)
    assert reopened.load_thesis_snapshot(aaa_t0.id) == aaa_t0
    assert reopened.load_thesis_snapshot(aaa_t3.id) == aaa_t3
    assert reopened.load_change_events(Ticker("AAA"))
    assert reopened.load_monitoring_events(entry.id)
    assert reopened.load_research_result("run-0:AAA") is not None
    assert reopened.load_backtest_run(persisted_balanced.id) == persisted_balanced
    # Adding later artifacts cannot mutate the frozen T0 interpretation.
    future_run = _run("run-4", date(2025, 3, 31), "balanced_value_quality")
    reopened.save_research_run(future_run)
    reopened.save_thesis_snapshot(thesis_engine.generate(future_run, _result(future_run, "AAA", 1, 90, 95, 12)))
    assert reopened.load_thesis_snapshot(aaa_t0.id) == aaa_t0
    reopened.close()


def _persist_theses(storage: SQLiteStorage, story: dict[str, tuple[ResearchRun, tuple[ResearchResult, ...]]]) -> dict[str, ThesisSnapshot]:
    engine = StructuredThesisEngine()
    snapshots: dict[str, ThesisSnapshot] = {}
    for run, results in story.values():
        for result in results:
            snapshot = engine.generate(run, result)
            storage.save_thesis_snapshot(snapshot)
            snapshots[snapshot.id] = snapshot
    return snapshots


def _persist_changes(storage: SQLiteStorage, story: dict[str, tuple[ResearchRun, tuple[ResearchResult, ...]]]) -> None:
    policy = MaterialityPolicy("wave_d_policy_v1", (
        MaterialityRule("rank", MaterialityRuleType.RANK_MOVEMENT, 1, "rank_v1"),
        MaterialityRule("classification", MaterialityRuleType.STATUS_TRANSITION, None, "class_v1"),
        MaterialityRule("composite_score", MaterialityRuleType.ABSOLUTE, 5, "score_v1"),
        MaterialityRule("factor:quality", MaterialityRuleType.ABSOLUTE, 5, "factor_v1"),
    ))
    for index in range(3):
        old_run, old_results = story[f"run-{index}"]
        new_run, new_results = story[f"run-{index + 1}"]
        for symbol in ("AAA", "DDD"):
            old = next(item for item in old_results if item.ticker.symbol == symbol)
            new = next(item for item in new_results if item.ticker.symbol == symbol)
            for event in compare_results(old_run, old, new_run, new, policy):
                storage.save_change_event(event)


def _persist_backtests(
    storage: SQLiteStorage,
    story: dict[str, tuple[ResearchRun, tuple[ResearchResult, ...]]],
) -> tuple[str, str]:
    prices = {
        DATES[0]: {symbol: 100.0 for symbol in SYMBOLS},
        DATES[1]: {symbol: 102.0 for symbol in SYMBOLS},
        DATES[2]: {symbol: 104.0 for symbol in SYMBOLS},
        DATES[3]: {symbol: 108.0 for symbol in SYMBOLS},
        date(2025, 3, 31): {symbol: 110.0 for symbol in SYMBOLS},
    }
    benchmark_prices = {when: 100.0 + index for index, when in enumerate(prices)}
    config = BacktestConfigV1(
        DATES[0], date(2025, 3, 31), 2, 1000.0, .01, "FIXTURE_BENCHMARK",
        CorporateActionMode.RAW_PRICES_EXPLICIT_ACTIONS,
    )
    balanced_runs = tuple(story.values())
    balanced = simulate_persisted_runs(balanced_runs, prices, benchmark_prices, config=config)
    graham_pairs = []
    for index, as_of in enumerate(DATES):
        _, results = story[f"run-{index}"]
        run = _run(f"graham-cli-{index}", as_of, "graham_defensive")
        converted = tuple(
            ResearchResult(
                f"{run.id}:{result.ticker.symbol}", run.id, result.ticker, run.created_at,
                result.rank, result.composite_score, result.classification,
                result.factor_scores, result.criteria,
            )
            for result in results
        )
        storage.save_research_run(run)
        for result in converted:
            storage.save_research_result(result)
        graham_pairs.append((run, converted))
    graham = simulate_persisted_runs(tuple(graham_pairs), prices, benchmark_prices, config=config)
    storage.save_backtest_run(balanced)
    storage.save_backtest_run(graham)
    return balanced.id, graham.id


def _persist_watchlist(storage: SQLiteStorage, story: dict[str, tuple[ResearchRun, tuple[ResearchResult, ...]]]) -> WatchlistEntry:
    entry = WatchlistEntry(
        "watch-aaa-cli", Ticker("AAA"), story["run-0"][0].created_at, "run-0", "run-0:AAA",
        "High quality, valuation initially too demanding", WatchlistStatus.ACTIVE,
        target_conditions=(WatchCondition("pe_ttm", "<=", 18, "watch_pe_v1"),),
    )
    storage.save_watchlist_entry(entry)
    previous: dict[str, object] = {}
    for run_id in ("run-0", "run-1", "run-2", "run-3"):
        run, results = story[run_id]
        result = next(item for item in results if item.ticker.symbol == "AAA")
        for event in evaluate_watchlist(entry, run, result, previous):
            storage.save_monitoring_event(event)
        previous = {
            "pe_ttm": next(item for item in result.criteria if item.criterion_name == "pe_ttm").observed,
            "classification": result.classification,
        }
    return entry


def test_wave_d_reopened_cli_has_provider_http_kill_switch(tmp_path, monkeypatch, capsys) -> None:
    """Historical inspection must remain offline after the database is reopened."""
    db_path = tmp_path / "wave-d-cli.sqlite"
    with SQLiteStorage(db_path) as storage:
        story = _persist_story(storage)
        _persist_theses(storage, story)
        _persist_changes(storage, story)
        _persist_watchlist(storage, story)
        balanced_id, graham_id = _persist_backtests(storage, story)

    def provider_kill_switch(*args: object, **kwargs: object) -> object:
        raise AssertionError("historical inspection touched a provider")

    monkeypatch.setattr("stocks_investment.data.providers.fixture.FixtureProvider.prices", provider_kill_switch)
    monkeypatch.setattr("stocks_investment.data.providers.fixture.FixtureProvider.quote", provider_kill_switch)
    monkeypatch.setattr("stocks_investment.data.providers.fixture.FixtureProvider.provenance", provider_kill_switch)
    monkeypatch.setattr("stocks_investment.data.providers.fixture.FixtureProvider.metric_inputs", provider_kill_switch)
    monkeypatch.setattr("stocks_investment.data.providers.sec.SecEdgarProvider.metric_inputs", provider_kill_switch)
    monkeypatch.setattr("stocks_investment.data.providers.sec.SecEdgarProvider._facts", provider_kill_switch)
    monkeypatch.setattr("stocks_investment.data.providers.alpha_vantage.AlphaVantageMarketProvider.prices", provider_kill_switch)
    monkeypatch.setattr("stocks_investment.data.providers.alpha_vantage.AlphaVantageMarketProvider.quote", provider_kill_switch)
    monkeypatch.setattr("stocks_investment.data.providers.alpha_vantage.AlphaVantageMarketProvider.corporate_actions", provider_kill_switch)
    monkeypatch.setattr("stocks_investment.data.providers._http.request_json", provider_kill_switch)

    with SQLiteStorage(db_path) as reopened:
        snapshots = reopened.load_thesis_snapshots(Ticker("AAA"))
        assert snapshots
        assert reopened.load_change_events(Ticker("AAA"))
        assert reopened.load_watchlist_entries()
        left = reopened.load_backtest_run(graham_id)
        right = reopened.load_backtest_run(balanced_id)
        assert left is not None and right is not None
        comparison = compare_backtests(left, right)
        assert comparison.metadata["compatible"] is True
        result = next(item for item in reopened.load_research_results("run-2") if item.ticker == Ticker("AAA"))
        outcome = reopened.load_research_outcomes(result.id)[0]
        quality = next(item for item in result.factor_scores if item.factor_name == "quality")
        observation = FactorOutcomeObservation(
            quality.factor_name, quality.factor_version, result.run_id, result.ticker,
            date(2024, 9, 30), quality.score, outcome.horizon, outcome.forward_return,
            outcome.benchmark_return, outcome.excess_return, "valid", "synthetic",
            "FIXTURE_BENCHMARK", "USD", "quarterly",
        )
        cohort = CohortIdentity("quality_v1", "synthetic", date(2024, 9, 30), date(2024, 9, 30), "12M", "quarterly", "USD", "FIXTURE_BENCHMARK")
        assert summarize_factor((observation,), cohort).sample_size == 1
        report = build_report(
            "historical_stock", snapshots[-1].as_of, tuple(item.research_run_id for item in snapshots),
            (ReportSection("RESEARCH AS OF", "research", {"snapshots": snapshots}),
             ReportSection("SUBSEQUENT OUTCOME", "outcome", {"outcomes": (outcome,)})),
        )
        assert json.loads(render_json(report))["sections"][0]["section_type"] == "research"
        assert "## SUBSEQUENT OUTCOME" in render_markdown(report)

    commands = (
        ["thesis", "AAA", "--db", str(db_path), "--format", "json"],
        ["thesis-history", "AAA", "--db", str(db_path), "--format", "json"],
        ["changes", "AAA", "--db", str(db_path), "--format", "json"],
        ["compare-strategies", graham_id, balanced_id, "--db", str(db_path), "--format", "json"],
        ["factor-efficacy", "quality", "--db", str(db_path), "--horizon", "12M", "--format", "json"],
        ["watchlist", "--db", str(db_path), "--format", "json"],
        ["report", "AAA", "--db", str(db_path), "--format", "json"],
    )
    first_outputs = []
    for command in commands:
        assert cli_main(command) == 0
        first_outputs.append(capsys.readouterr().out)
    for command, expected in zip(commands, first_outputs):
        assert cli_main(command) == 0
        assert capsys.readouterr().out == expected


def test_wave_d_adversarial_version_order_and_outcome_attacks(tmp_path) -> None:
    db_path = tmp_path / "wave-d-attacks.sqlite"
    with SQLiteStorage(db_path) as storage:
        story = _persist_story(storage)
        snapshots = _persist_theses(storage, story)
        entry = _persist_watchlist(storage, story)
        balanced_id, graham_id = _persist_backtests(storage, story)
        aaa_t0 = snapshots["thesis:run-0:AAA:structured_thesis_v1"]
        old_events = storage.load_change_events(Ticker("AAA"))
        old_monitoring = storage.load_monitoring_events(entry.id)
        old_backtest = storage.load_backtest_run(balanced_id)
        assert old_backtest is not None

        # Security order is deliberately changed. Identity-safe comparisons must remain stable.
        run0, results0 = story["run-0"]
        run1, results1 = story["run-1"]
        baseline = compare_rankings((run0, results0), (run1, results1), top_n=2)
        shuffled = compare_rankings((run0, tuple(reversed(results0))), (run1, tuple(reversed(results1))), top_n=2)
        assert shuffled.agreement_rate == baseline.agreement_rate
        assert shuffled.rank_correlation == baseline.rank_correlation

        # A +500% future outcome is outcome information only; it cannot mutate T0.
        future = ResearchOutcome("run-0:AAA", date(2025, 12, 31), "12M", 5.0, .02, 4.98)
        storage.save_research_outcome(future)
        assert storage.load_thesis_snapshot(aaa_t0.id) == aaa_t0
        assert storage.load_change_events(Ticker("AAA")) == old_events
        assert storage.load_monitoring_events(entry.id) == old_monitoring

        # New methodology versions are additive and cannot overwrite v1.
        v2 = ThesisSnapshot(
            "thesis:run-0:AAA:structured_thesis_v2", aaa_t0.ticker, aaa_t0.research_run_id,
            aaa_t0.research_result_id, aaa_t0.as_of, "structured_thesis_v2",
            aaa_t0.classification, aaa_t0.summary, aaa_t0.drivers, aaa_t0.assumptions,
            aaa_t0.invalidators, aaa_t0.structured_views, aaa_t0.confidence, aaa_t0.created_at,
        )
        storage.save_thesis_snapshot(v2)
        strategy_v2 = _run("run-strategy-v2", DATES[0], "balanced_value_quality")
        strategy_v2 = ResearchRun(
            strategy_v2.id, strategy_v2.created_at, strategy_v2.as_of, strategy_v2.strategy_name,
            "balanced_value_quality_v2", strategy_v2.universe_name, strategy_v2.universe_version,
            strategy_v2.universe_as_of, strategy_v2.parameters, strategy_v2.git_commit,
            strategy_v2.data_snapshot, strategy_v2.status,
        )
        storage.save_research_run(strategy_v2)
        assert storage.load_thesis_snapshot(aaa_t0.id) == aaa_t0
        assert storage.load_thesis_snapshot(v2.id) == v2
        assert storage.load_backtest_run(graham_id) is not None

        # The same report is deterministic and keeps future outcome semantically separate.
        report = build_report(
            "historical_stock", DATES[0], (aaa_t0.research_run_id,),
            (
                ReportSection("RESEARCH AS OF T0", "research", {"thesis": aaa_t0.summary},
                              (SourceReference("thesis_snapshot", aaa_t0.id),)),
                ReportSection("SUBSEQUENT OUTCOME", "outcome", {"forward_return": 5.0},
                              (SourceReference("research_outcome", future.result_id),)),
            ),
        )
        encoded = json.loads(render_json(report))
        assert [section["section_type"] for section in encoded["sections"]] == ["research", "outcome"]
        markdown = render_markdown(report)
        assert markdown.index("## RESEARCH AS OF T0") < markdown.index("## SUBSEQUENT OUTCOME")
        assert "5.0" not in markdown.split("## RESEARCH AS OF T0", 1)[1].split("## SUBSEQUENT OUTCOME", 1)[0]

    with SQLiteStorage(db_path) as reopened:
        assert reopened.load_thesis_snapshot(aaa_t0.id) == aaa_t0
        assert reopened.load_thesis_snapshot(v2.id) == v2
        assert reopened.load_change_events(Ticker("AAA")) == old_events
        assert reopened.load_monitoring_events(entry.id) == old_monitoring
        assert reopened.load_backtest_run(balanced_id) == old_backtest
        assert reopened.load_research_outcomes("run-0:AAA")[-1] == future
