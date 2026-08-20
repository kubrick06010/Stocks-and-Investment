"""Small read-only CLI for persisted research intelligence."""

from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
import json
import sys
from pathlib import Path
from typing import Any

from stocks_investment import __version__
from stocks_investment.comparison import compare_backtests
from stocks_investment.domain.research_engine import ResearchOutcome
from stocks_investment.domain.research_intelligence import CohortIdentity
from stocks_investment.domain.models import Ticker
from stocks_investment.factor_research import summarize_factor
from stocks_investment.interactive import (
    DeterministicInteractiveResearchService,
    render_research_view,
    run_session,
)
from stocks_investment.domain.interactive import (
    OutcomeVisibility,
    ResearchViewKind,
    ResearchViewRequest,
)
from stocks_investment.domain.narrative import NarrativePolicy, NarrativeRequest
from stocks_investment.narrative import StructuredNarrativeRenderer
from stocks_investment.reporting import (
    build_automation_run_report,
    build_filing_evidence_report,
    build_filing_history_report,
    build_historical_stock_report,
    render_json,
    render_markdown,
)
from stocks_investment.storage import ReadOnlySQLiteStorage, ReadOnlyStorageError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="stocks")
    parser.add_argument(
        "command",
        choices=(
            "version", "doctor", "thesis", "thesis-history", "changes", "watchlist",
            "compare-strategies", "factor-efficacy", "report", "filings", "filing-history",
            "automation-run",
            "narrative",
            "explore",
        ),
    )
    parser.add_argument("ticker", nargs="?")
    parser.add_argument("comparison_target", nargs="?")
    parser.add_argument("--db", type=Path, help="SQLite database containing persisted research")
    parser.add_argument("--format", choices=("text", "json", "markdown"), default="text")
    parser.add_argument("--backtest-a")
    parser.add_argument("--backtest-b")
    parser.add_argument("--factor-version")
    parser.add_argument("--horizon", default="12M")
    parser.add_argument("--as-of", type=date.fromisoformat)
    parser.add_argument("--outcomes", action="store_true", help="include clearly separated post-hoc outcomes")
    parser.add_argument("--json", action="store_true", dest="as_json", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.command == "version":
        result: Any = {"version": __version__}
    elif args.command == "doctor":
        result = {"status": "ok", "version": __version__, "storage": "not_configured"}
    else:
        if args.db is None:
            parser.error(f"{args.command} reads persisted history; --db is required")
        if args.command not in {
            "watchlist", "compare-strategies", "factor-efficacy", "explore",
        } and not args.ticker:
            parser.error(f"{args.command} requires a ticker")
        try:
            storage_context = ReadOnlySQLiteStorage(args.db)
        except ReadOnlyStorageError as exc:
            parser.error(str(exc))
        with storage_context as storage:
            if args.command == "explore":
                service = DeterministicInteractiveResearchService(storage)
                run_session(
                    service,
                    lambda view: render_research_view(view, args.format),
                )
                return 0
            if args.command == "narrative":
                service = DeterministicInteractiveResearchService(storage)
                request = ResearchViewRequest(
                    id=f"narrative:{args.ticker.upper()}:{args.as_of or ''}:{args.outcomes}",
                    kind=ResearchViewKind.STOCK,
                    methodology_version=service.version,
                    primary_id=args.ticker,
                    as_of=args.as_of,
                    outcome_visibility=(
                        OutcomeVisibility.SEPARATE if args.outcomes else OutcomeVisibility.EXCLUDE
                    ),
                )
                view = service.query(request)
                if view.report is None:
                    result = view
                else:
                    result = StructuredNarrativeRenderer().render(
                        NarrativeRequest(
                            view.report,
                            NarrativePolicy(
                                "structured", "structured_narrative_v1", include_outcomes=args.outcomes
                            ),
                        )
                    )
                if args.format == "json" or args.as_json:
                    print(json.dumps(result, default=_json_default, sort_keys=True))
                else:
                    print(result.text if hasattr(result, "text") else render_research_view(view, args.format))
                return 0
            if args.command in {"thesis", "thesis-history"}:
                result = {"ticker": args.ticker.upper(), "snapshots": storage.load_thesis_snapshots(Ticker(args.ticker))}
            elif args.command == "changes":
                result = {"ticker": args.ticker.upper(), "changes": storage.load_change_events(Ticker(args.ticker))}
            elif args.command == "watchlist":
                result = {"entries": storage.load_watchlist_entries()}
            elif args.command == "compare-strategies":
                left_id = args.backtest_a or args.ticker
                right_id = args.backtest_b or args.comparison_target
                if not left_id or not right_id:
                    parser.error("compare-strategies requires two backtest IDs or --backtest-a and --backtest-b")
                left = storage.load_backtest_run(left_id)
                right = storage.load_backtest_run(right_id)
                if left is None or right is None:
                    parser.error("backtest run not found")
                result = compare_backtests(left, right)
            elif args.command == "factor-efficacy":
                factor_version = _factor_version(args.ticker, args.factor_version)
                observations = list(storage.load_factor_outcome_observations(
                    factor_name=None, factor_version=factor_version
                ))
                observations = [item for item in observations if item.horizon == args.horizon]
                if not observations:
                    result = {"status": "insufficient_data", "factor_version": factor_version, "horizon": args.horizon}
                else:
                    identities = {
                        (item.universe, item.benchmark, item.base_currency, item.rebalance_cadence)
                        for item in observations
                    }
                    if len(identities) != 1:
                        result = {
                            "status": "incompatible_cohort",
                            "factor_version": factor_version,
                            "horizon": args.horizon,
                            "cohort_identities": sorted(identities),
                        }
                    else:
                        first = observations[0]
                        cohort = CohortIdentity(
                            factor_version, first.universe, min(item.as_of for item in observations),
                            max(item.as_of for item in observations), args.horizon,
                            first.rebalance_cadence, first.base_currency, first.benchmark,
                        )
                        result = summarize_factor(tuple(observations), cohort)
            elif args.command == "automation-run":
                automation_run = storage.load_automation_run(args.ticker)
                if automation_run is None:
                    parser.error("automation run not found")
                automation_definition = storage.load_automation_definition(
                    automation_run.definition_id, automation_run.definition_version
                )
                automation_trigger = storage.load_automation_trigger(automation_run.trigger_id)
                result = build_automation_run_report(
                    automation_run,
                    definition=automation_definition,
                    trigger=automation_trigger,
                )
            elif args.command in {"filings", "filing-history"}:
                ticker = Ticker(args.ticker)
                filings = storage.load_filings_available_on(ticker, args.as_of or date.max)
                if not filings:
                    result = {"status": "insufficient_data", "ticker": ticker.symbol}
                else:
                    current = filings[-1]
                    current_sections = storage.load_filing_sections(current.id)
                    current_claims = storage.load_qualitative_claims(filing_id=current.id)
                    if args.command == "filings":
                        result = build_filing_evidence_report(
                            current, current_sections, current_claims,
                            as_of=args.as_of or current.available_at.date(),
                        )
                    elif len(filings) < 2:
                        result = {
                            "status": "insufficient_history", "ticker": ticker.symbol,
                            "filings": len(filings),
                        }
                    else:
                        previous = filings[-2]
                        filing_changes = tuple(
                            item
                            for item in storage.load_filing_section_changes(ticker)
                            if item.from_filing_id == previous.id and item.to_filing_id == current.id
                        )
                        result = build_filing_history_report(
                            previous,
                            storage.load_filing_sections(previous.id),
                            current,
                            current_sections,
                            filing_changes,
                            current_claims,
                            as_of=args.as_of or current.available_at.date(),
                        )
            else:
                snapshots = storage.load_thesis_snapshots(Ticker(args.ticker))
                changes = storage.load_change_events(Ticker(args.ticker))
                entries = tuple(item for item in storage.load_watchlist_entries() if item.ticker == Ticker(args.ticker))
                monitoring = tuple(
                    event
                    for entry in entries
                    for event in storage.load_monitoring_events(entry.id)
                )
                outcomes: list[ResearchOutcome] = []
                for snapshot in snapshots:
                    outcomes.extend(storage.load_research_outcomes(snapshot.research_result_id))
                result = build_historical_stock_report(
                    args.ticker.upper(), snapshots, changes, entries, monitoring, outcomes
                )
        if args.format == "json" or args.as_json:
            print(render_json(result) if hasattr(result, "sections") else json.dumps(result, default=_json_default, sort_keys=True))
        elif args.format == "markdown":
            print(render_markdown(result) if hasattr(result, "sections") else "## Historical research\n\n" + _render_text(args.command, result))
        else:
            print(_render_text(args.command, result))
        return 0
    if args.format == "json" or args.as_json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(result["version"] if args.command == "version" else "stocks doctor: ok")
    return 0


def _json_default(value: object) -> object:
    if is_dataclass(value):
        return asdict(value)  # type: ignore[arg-type]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"unsupported value: {type(value).__name__}")


def _render_text(command: str, result: Any) -> str:
    data = result
    if command == "compare-strategies":
        return "\n".join(
            f"{key}: {value}"
            for key, value in (
                ("strategy_a", data.strategy_a),
                ("strategy_b", data.strategy_b),
                ("compatibility", not data.assumption_mismatches),
                ("mismatches", data.assumption_mismatches),
                ("return_a", data.return_a),
                ("return_b", data.return_b),
                ("turnover_a", data.turnover_a),
                ("turnover_b", data.turnover_b),
                ("metadata", data.metadata),
            )
        )
    if command == "factor-efficacy":
        if isinstance(data, dict):
            return "\n".join(f"{key}: {value}" for key, value in sorted(data.items()))
        return "\n".join(
            f"{key}: {value}"
            for key, value in (
                ("factor", data.factor_name),
                ("factor_version", data.factor_version),
                ("horizon", data.cohort.outcome_horizon),
                ("sample_size", data.sample_size),
                ("coverage", data.coverage),
                ("mean_forward_return", data.mean_forward_return),
                ("mean_excess_return", data.mean_excess_return),
                ("spread", data.spread),
                ("rank_ic", data.rank_ic),
                ("hit_rate", data.hit_rate),
                ("metadata", data.metadata),
            )
        )
    if command == "watchlist":
        return "\n".join(f"{item.id}: {item.ticker.symbol} [{item.status.value}] {item.reason}" for item in data["entries"])
    if command in {"thesis", "thesis-history"}:
        return "\n".join(f"{item.as_of}: {item.classification.value} ({item.thesis_version})" for item in data["snapshots"])
    if command in {"filings", "filing-history"} and isinstance(data, dict):
        return "\n".join(f"{key}: {value}" for key, value in sorted(data.items()))
    if command in {"report", "filings", "filing-history", "automation-run"}:
        return render_markdown(data)
    return "\n".join(f"{item.to_as_of}: {item.change_type.value} {item.field}" for item in data["changes"])


def _factor_version(name: str | None, explicit: str | None) -> str:
    if explicit:
        return explicit
    aliases = {
        "quality": "quality_v1",
        "value": "value_v1",
        "composite": "balanced_value_quality_v1",
    }
    return aliases.get((name or "quality").lower(), name or "quality_v1")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
