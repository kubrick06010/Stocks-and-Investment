from dataclasses import replace
from datetime import date, datetime, timezone

from stocks_investment.cli import main
import pytest

from stocks_investment.backtesting import BacktestConfigV1, BacktestPeriod, BacktestRun
from stocks_investment.domain import (
    DataProvenance,
    FilingDocument,
    FilingForm,
    ResearchRun,
    ResearchRunStatus,
    Ticker,
)
from stocks_investment.domain.research_engine import ResearchOutcome
from stocks_investment.domain.research_intelligence import (
    FactorOutcomeObservation,
    ThesisClassification,
    ThesisSnapshot,
)
from stocks_investment.storage import SQLiteStorage


def test_historical_cli_reads_persisted_thesis(tmp_path, capsys) -> None:
    path = tmp_path / "history.sqlite"
    run = ResearchRun("r", datetime(2025, 1, 1, tzinfo=timezone.utc), date(2025, 1, 1), "s", "s_v1", "u", "u_v1", date(2025, 1, 1), status=ResearchRunStatus.COMPLETED)
    snapshot = ThesisSnapshot("t", Ticker("AAA"), run.id, "r:AAA", run.as_of, "structured_thesis_v1", ThesisClassification.WATCH, "watch")
    with SQLiteStorage(path) as storage:
        storage.save_research_run(run)
        storage.save_thesis_snapshot(snapshot)
    assert main(["thesis-history", "AAA", "--db", str(path), "--format", "json"]) == 0
    assert "structured_thesis_v1" in capsys.readouterr().out


def test_report_reads_persisted_history_and_separates_outcomes(tmp_path, capsys) -> None:
    path = tmp_path / "report.sqlite"
    run = ResearchRun("r", datetime(2025, 1, 1, tzinfo=timezone.utc), date(2025, 1, 1), "s", "s_v1", "u", "u_v1", date(2025, 1, 1), status=ResearchRunStatus.COMPLETED)
    snapshot = ThesisSnapshot("t", Ticker("AAA"), run.id, "r:AAA", run.as_of, "structured_thesis_v1", ThesisClassification.WATCH, "watch")
    with SQLiteStorage(path) as storage:
        storage.save_research_run(run)
        storage.save_thesis_snapshot(snapshot)
        storage.save_research_outcome(ResearchOutcome("r:AAA", date(2026, 1, 1), "12M", .25, .10, .15))

    assert main(["report", "AAA", "--db", str(path), "--format", "json"]) == 0
    output = capsys.readouterr().out
    assert '"section_type": "research"' in output
    assert '"section_type": "outcome"' in output
    assert '"entity_type": "thesis_snapshot"' in output
    assert '"entity_type": "research_outcome"' in output


def test_compare_strategies_accepts_two_persisted_ids_and_json_is_deterministic(tmp_path, capsys) -> None:
    path = tmp_path / "comparison.sqlite"
    config = BacktestConfigV1(date(2024, 1, 1), date(2025, 1, 1), 1, 100.0, .01, "BENCH")
    period = BacktestPeriod(0, "research", date(2024, 1, 1), date(2024, 1, 1), date(2025, 1, 1), 100.0, 110.0, .10, .20, 2.0, .08, .05, .03, ("AAA",))
    left = BacktestRun("bt-a", "graham", "v1", config, (period,), 110.0)
    right = BacktestRun("bt-b", "balanced", "v1", config, (period,), 110.0)
    with SQLiteStorage(path) as storage:
        storage.save_backtest_run(left)
        storage.save_backtest_run(right)

    assert main(["compare-strategies", "bt-a", "bt-b", "--db", str(path), "--format", "json"]) == 0
    first = capsys.readouterr().out
    assert '"strategy_a": "graham"' in first
    assert '"transaction_costs": 2.0' in first
    assert main(["compare-strategies", "--backtest-a", "bt-a", "--backtest-b", "bt-b", "--db", str(path), "--format", "json"]) == 0
    second = capsys.readouterr().out
    assert first == second


def test_factor_efficacy_cli_reads_persisted_observations(tmp_path, capsys) -> None:
    path = tmp_path / "factor.sqlite"
    with SQLiteStorage(path) as storage:
        for index in range(1, 6):
            storage.save_factor_outcome_observation(
                FactorOutcomeObservation(
                    "quality", "quality_v1", f"run-{index}", Ticker(f"A{index}"), date(2024, 3, 31), float(index), "12M", .1 * index, .02, .1 * index - .02, "measured", "synthetic", "SYNTH", "USD", "quarterly",
                )
            )

    assert main(["factor-efficacy", "quality", "--db", str(path), "--horizon", "12M", "--format", "json"]) == 0
    output = capsys.readouterr().out
    assert '"factor_version": "quality_v1"' in output
    assert '"cohort"' in output
    assert '"coverage": 1.0' in output


def test_factor_efficacy_cli_reports_mixed_cohort_without_traceback(tmp_path, capsys) -> None:
    path = tmp_path / "mixed-factor.sqlite"
    with SQLiteStorage(path) as storage:
        for ticker, universe in (("AAA", "SP500"), ("BBB", "NASDAQ")):
            storage.save_factor_outcome_observation(
                FactorOutcomeObservation(
                    "quality", "quality_v1", f"run-{ticker}", Ticker(ticker),
                    date(2024, 3, 31), 80, "12M", .1, .02, .08, "measured",
                    universe, "SYNTH", "USD", "quarterly",
                )
            )
    assert main(["factor-efficacy", "quality", "--db", str(path), "--format", "json"]) == 0
    output = capsys.readouterr().out
    assert '"status": "incompatible_cohort"' in output
    assert "Traceback" not in output


def test_expected_missing_and_incompatible_cli_inputs_have_no_traceback(tmp_path, capsys) -> None:
    path = tmp_path / "empty.sqlite"
    with SQLiteStorage(path):
        pass
    assert main(["report", "MISSING", "--db", str(path), "--format", "json"]) == 0
    assert "Traceback" not in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["compare-strategies", "--db", str(path)])
    assert "Traceback" not in capsys.readouterr().err


@pytest.mark.parametrize(
    ("command", "extra"),
    (
        ("thesis", ("MISSING",)),
        ("thesis-history", ("MISSING",)),
        ("changes", ("MISSING",)),
        ("watchlist", ()),
        ("factor-efficacy", ("quality",)),
        ("report", ("MISSING",)),
        ("filings", ("MISSING",)),
        ("filing-history", ("MISSING",)),
    ),
)
@pytest.mark.parametrize("output_format", ("text", "json", "markdown"))
def test_historical_commands_support_all_output_formats_on_empty_history(
    tmp_path, capsys, command, extra, output_format
) -> None:
    path = tmp_path / f"{command}-{output_format}.sqlite"
    with SQLiteStorage(path):
        pass
    assert main([command, *extra, "--db", str(path), "--format", output_format]) == 0
    output = capsys.readouterr().out
    assert output
    assert "Traceback" not in output


def test_compare_strategies_cli_reports_incompatibility_without_a_winner(tmp_path, capsys) -> None:
    path = tmp_path / "incompatible.sqlite"
    base = BacktestConfigV1(date(2024, 1, 1), date(2025, 1, 1), 1, 100.0, .01, "BENCH")
    other = replace(base, benchmark="OTHER")
    period = BacktestPeriod(0, "research", date(2024, 1, 1), date(2024, 1, 1), date(2025, 1, 1), 100.0, 110.0, .10, .20, 2.0, .08, .05, .03, ("AAA",))
    with SQLiteStorage(path) as storage:
        storage.save_backtest_run(BacktestRun("left", "strategy", "v1", base, (period,), 110.0))
        storage.save_backtest_run(BacktestRun("right", "strategy", "v1", other, (period,), 110.0))

    assert main(["compare-strategies", "left", "right", "--db", str(path), "--format", "json"]) == 0
    output = capsys.readouterr().out
    assert '"compatible": false' in output
    assert '"benchmark"' in output
    assert '"return_a": null' in output


def test_filing_cli_reads_only_persisted_pit_evidence(tmp_path, capsys) -> None:
    path = tmp_path / "filings.sqlite"
    available = datetime(2025, 2, 14, 21, tzinfo=timezone.utc)
    provenance = DataProvenance(
        "sec:archive", "sec-edgar", available, available.date(), available_at=available,
        filing_date=available.date(), raw_identifier="0001/filing.htm",
    )
    filing = FilingDocument(
        "filing-1", Ticker("AAA"), "0000000001", "0001-25-000001",
        FilingForm.FORM_10_K, available, available, date(2024, 12, 31), "filing.htm",
        "https://www.sec.gov/Archives/filing.htm", "sha256:filing", available,
        "text/html", 100, provenance,
    )
    with SQLiteStorage(path) as storage:
        storage.save_filing_document(filing)

    assert main(["filings", "AAA", "--db", str(path), "--format", "json"]) == 0
    output = capsys.readouterr().out
    assert '"report_type": "filing_evidence"' in output
    assert '"filing_document"' in output
    assert main([
        "filings", "AAA", "--db", str(path), "--as-of", "2025-02-13", "--format", "json",
    ]) == 0
    assert '"status": "insufficient_data"' in capsys.readouterr().out
