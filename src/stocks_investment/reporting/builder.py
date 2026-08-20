"""D6 reports: presentation of structured inputs, never analytical recomputation."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from enum import Enum
from typing import Iterable, Sequence

from stocks_investment.domain.research_engine import ResearchOutcome
from stocks_investment.domain.research_intelligence import ReportSection, ResearchReport
from stocks_investment.domain.research_intelligence import (
    ResearchChangeEvent,
    SourceReference,
    ThesisSnapshot,
    WatchlistEntry,
)
from stocks_investment.domain.research_intelligence import MonitoringEvent


def build_report(
    report_type: str,
    as_of: date,
    source_run_ids: Iterable[str],
    sections: Iterable[ReportSection],
    *,
    metadata: dict[str, object] | None = None,
) -> ResearchReport:
    return ResearchReport(
        report_type, as_of, tuple(source_run_ids), tuple(sections), metadata or {}
    )


def render_json(report: ResearchReport) -> str:
    return json.dumps(asdict(report), default=_json_default, sort_keys=True)


def render_markdown(report: ResearchReport) -> str:
    lines = [
        f"# {report.report_type}",
        f"As-of: {report.as_of.isoformat()}",
        "",
        f"Source runs: {', '.join(report.source_run_ids)}",
    ]
    for section in report.sections:
        lines.extend(["", f"## {section.title}"])
        lines.append(f"Section type: {section.section_type}")
        if section.source_references:
            lines.append(
                "Sources: "
                + ", ".join(
                    f"{item.entity_type}:{item.entity_id}"
                    + (f".{item.field}" if item.field else "")
                    for item in section.source_references
                )
            )
        for key, value in sorted(section.payload.items()):
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def build_historical_stock_report(
    ticker: str,
    snapshots: Sequence[ThesisSnapshot],
    changes: Sequence[ResearchChangeEvent],
    watchlist_entries: Sequence[WatchlistEntry],
    monitoring_events: Sequence[MonitoringEvent],
    outcomes: Sequence[ResearchOutcome],
) -> ResearchReport:
    """Assemble a persisted historical report without recalculating research.

    Research and post-hoc outcomes are separate canonical sections.  The
    function accepts already loaded domain objects so it cannot fetch current
    data or silently regenerate an old decision.
    """
    ordered_snapshots = tuple(sorted(snapshots, key=lambda item: (item.as_of, item.id)))
    as_of = ordered_snapshots[-1].as_of if ordered_snapshots else date.today()
    run_ids = tuple(dict.fromkeys(item.research_run_id for item in ordered_snapshots))
    snapshot_refs = tuple(SourceReference("thesis_snapshot", item.id) for item in ordered_snapshots)
    change_refs = tuple(
        SourceReference("research_change_event", f"{item.from_run_id}->{item.to_run_id}:{item.field}")
        for item in changes
    )
    watch_refs = tuple(SourceReference("watchlist_entry", item.id) for item in watchlist_entries)
    monitoring_refs = tuple(
        SourceReference("monitoring_event", f"{item.watchlist_entry_id}:{item.research_run_id}")
        for item in monitoring_events
    )
    outcome_refs = tuple(
        SourceReference("research_outcome", f"{item.result_id}:{item.horizon}:{item.measured_at}")
        for item in outcomes
    )
    research_sections = (
        ReportSection(
            "CURRENT RESEARCH STATE",
            "research",
            {"ticker": ticker, "latest_snapshot": ordered_snapshots[-1] if ordered_snapshots else None},
            snapshot_refs[-1:] if snapshot_refs else (),
        ),
        ReportSection(
            "THESIS HISTORY",
            "research",
            {"snapshots": ordered_snapshots},
            snapshot_refs,
        ),
        ReportSection(
            "MATERIAL CHANGES",
            "research",
            {"changes": tuple(changes)},
            change_refs,
        ),
        ReportSection(
            "WATCHLIST",
            "research",
            {"entries": tuple(watchlist_entries)},
            watch_refs,
        ),
        ReportSection(
            "MONITORING HISTORY",
            "research",
            {"events": tuple(monitoring_events)},
            monitoring_refs,
        ),
    )
    outcome_section = ReportSection(
        "SUBSEQUENT OUTCOME",
        "outcome",
        {"outcomes": tuple(outcomes)},
        outcome_refs,
    )
    return build_report(
        "historical_stock",
        as_of,
        run_ids,
        (*research_sections, outcome_section),
        metadata={"ticker": ticker, "information_boundary": "research_then_outcome"},
    )


def _json_default(value: object) -> object:
    if isinstance(value, (date, Enum)):
        return value.value if isinstance(value, Enum) else value.isoformat()
    raise TypeError(f"unsupported report value: {type(value).__name__}")
