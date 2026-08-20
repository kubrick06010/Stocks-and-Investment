"""Provider-free read service for persisted research intelligence.

The service is deliberately a thin application adapter.  It only calls the
read methods exposed by an already-open storage object and delegates analytical
work to the validated Wave C/D builders.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable

from stocks_investment.comparison import compare_backtests
from stocks_investment.domain.interactive import (
    OutcomeVisibility,
    ResearchView,
    ResearchViewKind,
    ResearchViewLink,
    ResearchViewRequest,
    ResearchViewStatus,
)
from stocks_investment.domain.models import Ticker
from stocks_investment.domain.research_intelligence import (
    CohortIdentity,
    ReportSection,
    ResearchReport,
    SourceReference,
)
from stocks_investment.factor_research import summarize_factor
from stocks_investment.reporting import (
    build_automation_run_report,
    build_filing_evidence_report,
    build_filing_history_report,
    build_historical_stock_report,
    build_portfolio_construction_report,
    build_report,
)


@dataclass(frozen=True, slots=True)
class _Loaded:
    report: ResearchReport
    references: tuple[SourceReference, ...]
    links: tuple[ResearchViewLink, ...] = ()
    warnings: tuple[str, ...] = ()
    status: ResearchViewStatus = ResearchViewStatus.VALID


class DeterministicInteractiveResearchService:
    """Query immutable local evidence without providers or current-data fallback."""

    version = "interactive_research_v1"

    def __init__(self, reader: Any, *, version: str | None = None) -> None:
        self._reader = reader
        self.version = version or self.version

    def query(self, request: ResearchViewRequest) -> ResearchView:
        if request.methodology_version != self.version:
            return ResearchView(
                request.id,
                ResearchViewStatus.INCOMPATIBLE,
                self._status_report(request, "incompatible", {"methodology_version": request.methodology_version}),
                (),
                (),
                (f"unsupported methodology version: {request.methodology_version}",),
            )
        try:
            loaded = self._dispatch(request)
        except ValueError as error:
            return ResearchView(request.id, ResearchViewStatus.INVALID_REQUEST, None, (), (), (str(error),))
        if loaded is None:
            return ResearchView(request.id, ResearchViewStatus.NOT_FOUND, None, (), (), ("persisted evidence not found",))
        refs = _unique_refs(loaded.references)
        return ResearchView(
            request.id,
            loaded.status,
            loaded.report,
            loaded.links,
            refs,
            loaded.warnings,
        )

    def _dispatch(self, request: ResearchViewRequest) -> _Loaded | None:
        handlers = {
            ResearchViewKind.STOCK: self._stock,
            ResearchViewKind.THESIS_HISTORY: self._thesis_history,
            ResearchViewKind.CHANGES: self._changes,
            ResearchViewKind.WATCHLIST: self._watchlist,
            ResearchViewKind.FILING: self._filing,
            ResearchViewKind.FILING_HISTORY: self._filing_history,
            ResearchViewKind.BACKTEST: self._backtest,
            ResearchViewKind.STRATEGY_COMPARISON: self._strategy_comparison,
            ResearchViewKind.FACTOR_EFFICACY: self._factor_efficacy,
            ResearchViewKind.AUTOMATION_RUN: self._automation_run,
            ResearchViewKind.PORTFOLIO_CONSTRUCTION: self._portfolio_construction,
        }
        return handlers[request.kind](request)

    def _stock(self, request: ResearchViewRequest) -> _Loaded | None:
        ticker = Ticker(_identifier(request.primary_id))
        snapshots = tuple(item for item in self._reader.load_thesis_snapshots(ticker) if _visible(item, request.as_of))
        if not snapshots:
            return None
        snapshots = snapshots[-request.limit :]
        changes = tuple(
            item for item in self._reader.load_change_events(ticker)
            if request.as_of is None or item.to_as_of <= request.as_of
        )[-request.limit :]
        entries = tuple(
            item for item in self._reader.load_watchlist_entries()
            if item.ticker == ticker and _created_visible(item, request.as_of)
        )[:request.limit]
        monitoring = tuple(
            event
            for entry in entries
            for event in self._reader.load_monitoring_events(entry.id)
            if _visible(event, request.as_of)
        )[:request.limit]
        outcomes: list[Any] = []
        if request.outcome_visibility is OutcomeVisibility.SEPARATE:
            for snapshot in snapshots:
                outcomes.extend(self._reader.load_research_outcomes(snapshot.research_result_id))
            outcomes = outcomes[:request.limit]
        report = build_historical_stock_report(
            ticker.symbol, snapshots, changes, entries, monitoring,
            tuple(outcomes) if request.outcome_visibility is OutcomeVisibility.SEPARATE else (),
        )
        refs = tuple(
            [SourceReference("thesis_snapshot", item.id) for item in snapshots]
            + [SourceReference("research_change_event", f"{item.from_run_id}->{item.to_run_id}:{item.field}") for item in changes]
            + [SourceReference("watchlist_entry", item.id) for item in entries]
            + [SourceReference("monitoring_event", f"{item.watchlist_entry_id}:{item.research_run_id}") for item in monitoring]
            + [SourceReference("research_outcome", f"{item.result_id}:{item.horizon}:{item.measured_at}") for item in outcomes]
        )
        links = (
            ResearchViewLink("thesis history", ResearchViewKind.THESIS_HISTORY, ticker.symbol, as_of=request.as_of),
            ResearchViewLink("changes", ResearchViewKind.CHANGES, ticker.symbol, as_of=request.as_of),
        )
        warnings = () if request.outcome_visibility is OutcomeVisibility.EXCLUDE else ("outcomes are post-hoc and are kept in a separate report section",)
        return _Loaded(report, refs, links, warnings)

    def _thesis_history(self, request: ResearchViewRequest) -> _Loaded | None:
        ticker = Ticker(_identifier(request.primary_id))
        snapshots = tuple(item for item in self._reader.load_thesis_snapshots(ticker) if _visible(item, request.as_of))[-request.limit :]
        if not snapshots:
            return None
        refs = tuple(SourceReference("thesis_snapshot", item.id) for item in snapshots)
        report = self._simple_report("thesis_history", _report_date(request, snapshots), snapshots, refs)
        return _Loaded(report, refs)

    def _changes(self, request: ResearchViewRequest) -> _Loaded | None:
        ticker = Ticker(_identifier(request.primary_id))
        changes = tuple(item for item in self._reader.load_change_events(ticker)
                        if request.as_of is None or item.to_as_of <= request.as_of)[-request.limit :]
        if not changes:
            return None
        refs = tuple(SourceReference("research_change_event", f"{item.from_run_id}->{item.to_run_id}:{item.field}") for item in changes)
        return _Loaded(self._simple_report("research_changes", _report_date(request, changes), changes, refs), refs)

    def _watchlist(self, request: ResearchViewRequest) -> _Loaded | None:
        entries = tuple(
            item for item in self._reader.load_watchlist_entries()
            if _created_visible(item, request.as_of)
        )[:request.limit]
        if not entries:
            return None
        refs = tuple(SourceReference("watchlist_entry", item.id) for item in entries)
        events = tuple(
            event
            for entry in entries
            for event in self._reader.load_monitoring_events(entry.id)
            if _visible(event, request.as_of)
        )[:request.limit]
        refs += tuple(SourceReference("monitoring_event", f"{event.watchlist_entry_id}:{event.research_run_id}") for event in events)
        report = self._simple_report("watchlist", _report_date(request, entries), {"entries": entries, "events": events}, refs)
        return _Loaded(report, refs, warnings=("watchlist entries are evaluated from persisted research runs only",))

    def _filing(self, request: ResearchViewRequest) -> _Loaded | None:
        ticker = Ticker(_identifier(request.primary_id))
        filings = self._reader.load_filings_available_on(ticker, request.as_of or date.max)
        if not filings:
            return None
        filing = filings[-1]
        sections = self._reader.load_filing_sections(filing.id)
        claims = self._reader.load_qualitative_claims(filing_id=filing.id)
        report = build_filing_evidence_report(filing, sections, claims, as_of=request.as_of or filing.available_at.date())
        refs = (SourceReference("filing_document", filing.id),) + tuple(SourceReference("filing_section", item.id) for item in sections[:request.limit])
        return _Loaded(report, refs)

    def _filing_history(self, request: ResearchViewRequest) -> _Loaded | None:
        ticker = Ticker(_identifier(request.primary_id))
        filings = self._reader.load_filings_available_on(ticker, request.as_of or date.max)
        if len(filings) < 2:
            return None
        current, previous = filings[-1], filings[-2]
        changes = tuple(item for item in self._reader.load_filing_section_changes(ticker)
                        if item.from_filing_id == previous.id and item.to_filing_id == current.id)
        claims = self._reader.load_qualitative_claims(filing_id=current.id)
        report = build_filing_history_report(
            previous, self._reader.load_filing_sections(previous.id), current,
            self._reader.load_filing_sections(current.id), changes, claims,
            as_of=request.as_of or current.available_at.date(),
        )
        refs = (SourceReference("filing_document", previous.id), SourceReference("filing_document", current.id))
        return _Loaded(report, refs)

    def _backtest(self, request: ResearchViewRequest) -> _Loaded | None:
        run = self._reader.load_backtest_run(_identifier(request.primary_id))
        if run is None:
            return None
        if request.as_of is not None and run.config.end > request.as_of:
            return None
        refs = [SourceReference("backtest_run", run.id)]
        refs.extend(SourceReference("research_run", period.research_run_id) for period in run.periods[:request.limit])
        report = self._simple_report(
            "backtest", request.as_of or run.config.end, run, refs, section_type="outcome"
        )
        return _Loaded(report, tuple(refs))

    def _strategy_comparison(self, request: ResearchViewRequest) -> _Loaded | None:
        left = self._reader.load_backtest_run(_identifier(request.primary_id))
        right = self._reader.load_backtest_run(_identifier(request.secondary_id))
        if left is None or right is None:
            return None
        if request.as_of is not None and (left.config.end > request.as_of or right.config.end > request.as_of):
            return None
        comparison = compare_backtests(left, right)
        refs = (SourceReference("backtest_run", left.id), SourceReference("backtest_run", right.id))
        status = ResearchViewStatus.VALID if not comparison.assumption_mismatches else ResearchViewStatus.INCOMPATIBLE
        report = self._simple_report(
            "strategy_comparison", request.as_of or comparison.period_end, comparison, refs,
            metadata={"performance_comparable": not comparison.assumption_mismatches},
            section_type="outcome",
        )
        warnings = tuple(f"incompatible assumption: {item}" for item in comparison.assumption_mismatches)
        return _Loaded(report, refs, status=status, warnings=warnings)

    def _factor_efficacy(self, request: ResearchViewRequest) -> _Loaded | None:
        observations = tuple(self._reader.load_factor_outcome_observations(factor_name=request.primary_id, factor_version=request.factor_version))
        observations = tuple(item for item in observations if item.horizon == request.horizon and _visible(item, request.as_of))
        if not observations:
            return None
        identities = {(item.universe, item.benchmark, item.base_currency, item.rebalance_cadence) for item in observations}
        if len(identities) != 1:
            refs = tuple(SourceReference("factor_outcome_observation", f"{item.research_run_id}:{item.ticker.symbol}:{item.horizon}") for item in observations)
            report = self._simple_report(
                "factor_efficacy", _report_date(request, observations), observations, refs,
                metadata={"status": "incompatible_cohort"}, section_type="outcome",
            )
            return _Loaded(report, refs, status=ResearchViewStatus.INCOMPATIBLE, warnings=("factor observations belong to incompatible cohorts",))
        first = observations[0]
        cohort = CohortIdentity(first.factor_version, first.universe, min(item.as_of for item in observations),
                                max(item.as_of for item in observations), request.horizon or first.horizon,
                                first.rebalance_cadence, first.base_currency, first.benchmark)
        summary = summarize_factor(observations[:request.limit], cohort)
        refs = tuple(SourceReference("factor_outcome_observation", f"{item.research_run_id}:{item.ticker.symbol}:{item.horizon}") for item in observations[:request.limit])
        return _Loaded(self._simple_report(
                           "factor_efficacy", _report_date(request, observations), summary,
                           refs, section_type="outcome"), refs,
                       status=ResearchViewStatus.INSUFFICIENT_DATA if summary.metadata.get("status") else ResearchViewStatus.VALID)

    def _automation_run(self, request: ResearchViewRequest) -> _Loaded | None:
        run = self._reader.load_automation_run(_identifier(request.primary_id))
        if run is None:
            return None
        if request.as_of is not None and run.as_of > request.as_of:
            return None
        definition = self._reader.load_automation_definition(run.definition_id, run.definition_version)
        trigger = self._reader.load_automation_trigger(run.trigger_id)
        report = build_automation_run_report(run, definition=definition, trigger=trigger)
        refs = (SourceReference("automation_run", run.id), SourceReference("automation_definition", run.definition_id), SourceReference("automation_trigger", run.trigger_id))
        return _Loaded(report, refs)

    def _portfolio_construction(self, request: ResearchViewRequest) -> _Loaded | None:
        result = self._reader.load_portfolio_construction_result(_identifier(request.primary_id))
        if result is None:
            return None
        construction_request = self._reader.load_portfolio_construction_request(result.request_id)
        if construction_request is None:
            return self._incomplete(request, "portfolio construction request is missing")
        if request.as_of is not None and construction_request.as_of > request.as_of:
            return None
        policy = self._reader.load_portfolio_construction_policy(construction_request.policy_name, construction_request.policy_version)
        if policy is None:
            return self._incomplete(request, "portfolio construction policy is missing")
        report = build_portfolio_construction_report(construction_request, policy, result)
        refs = tuple(report.sections[-1].source_references)
        return _Loaded(report, refs, status=ResearchViewStatus.INSUFFICIENT_DATA if result.status.value != "valid" else ResearchViewStatus.VALID)

    def _incomplete(self, request: ResearchViewRequest, warning: str) -> _Loaded:
        report = self._status_report(request, "insufficient_data", {"warning": warning})
        return _Loaded(report, (), warnings=(warning,), status=ResearchViewStatus.INSUFFICIENT_DATA)

    def _simple_report(
        self,
        report_type: str,
        as_of: date,
        payload: object,
        refs: Iterable[SourceReference],
        *,
        metadata: dict[str, object] | None = None,
        section_type: str = "research",
    ) -> ResearchReport:
        refs_tuple = _unique_refs(tuple(refs))
        section = ReportSection(report_type.upper(), section_type, {"data": payload}, refs_tuple)
        runs = tuple(ref.entity_id for ref in refs_tuple if ref.entity_type == "research_run")
        return build_report(report_type, as_of, runs, (section,), metadata=metadata)

    def _status_report(self, request: ResearchViewRequest, status: str, payload: object) -> ResearchReport:
        return self._simple_report(request.kind.value, request.as_of or date.min, payload, (), metadata={"status": status})


def _identifier(value: str | None) -> str:
    if value is None or not value.strip():
        raise ValueError("view identifier is required")
    return value


def _visible(item: object, as_of: date | None) -> bool:
    if as_of is None:
        return True
    value = getattr(item, "as_of", None)
    if isinstance(value, date):
        return value <= as_of
    value = getattr(item, "available_at", None)
    date_method = getattr(value, "date", None)
    if callable(date_method):
        return bool(date_method() <= as_of)
    return True


def _created_visible(item: object, as_of: date | None) -> bool:
    if as_of is None:
        return True
    created_at = getattr(item, "created_at", None)
    if isinstance(created_at, datetime):
        return bool(created_at.date() <= as_of)
    return _visible(item, as_of)


def _report_date(request: ResearchViewRequest, items: Iterable[object]) -> date:
    if request.as_of is not None:
        return request.as_of
    item_values = tuple(items)
    dates = [value for item in item_values for value in (getattr(item, "as_of", None), getattr(item, "to_as_of", None), getattr(item, "measured_at", None)) if isinstance(value, date)]
    dates.extend(
        value.date()
        for item in item_values
        for value in (getattr(item, "created_at", None),)
        if isinstance(value, datetime)
    )
    return max(dates) if dates else date.min


def _unique_refs(references: Iterable[SourceReference]) -> tuple[SourceReference, ...]:
    result: list[SourceReference] = []
    seen: set[tuple[str, str, str | None]] = set()
    for reference in references:
        identity = (reference.entity_type, reference.entity_id, reference.field)
        if identity not in seen:
            seen.add(identity)
            result.append(reference)
    return tuple(result)
