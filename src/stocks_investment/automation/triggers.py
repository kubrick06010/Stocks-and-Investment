"""Deterministic construction of research-automation triggers.

This module is deliberately a trigger factory, not an executor or scheduler
daemon.  It consumes immutable definitions and, for filing triggers, a reader
of already-persisted filing documents.  It never calls providers.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import date, datetime, timezone
from typing import Protocol

from stocks_investment.domain.automation import (
    AutomationTrigger,
    AutomationTriggerKind,
    ResearchAutomationDefinition,
)
from stocks_investment.domain.filings import FilingDocument
from stocks_investment.domain.models import Ticker
from stocks_investment.domain.research_intelligence import SourceReference


class PersistedFilingReader(Protocol):
    """Read filings already stored locally; implementations must not fetch."""

    def load_filings_available_on(self, ticker: Ticker, as_of: date) -> tuple[FilingDocument, ...]: ...


def build_manual_trigger(
    definition: ResearchAutomationDefinition,
    *,
    as_of: date,
    observed_at: datetime,
) -> AutomationTrigger:
    """Build one reproducible manual trigger for a definition.

    ``observed_at`` is injected so a replay does not depend on wall-clock
    time.  The manual request is intentionally keyed by definition version
    and research date; replaying it produces the same identity.
    """

    _validate_definition(definition, AutomationTriggerKind.MANUAL)
    return _trigger(
        definition,
        AutomationTriggerKind.MANUAL,
        observed_at,
        as_of,
        (),
        (),
        f"manual:{definition.id}:{definition.version}:{as_of.isoformat()}",
        {"source": "manual"},
    )


class ScheduledTriggerSource:
    """Construct due scheduled triggers for an injected observation time.

    V1 accepts a small UTC cron subset: five fields (minute, hour, day of
    month, month, day of week), with ``*``, comma-separated integers and
    inclusive ranges.  A definition is due when all fields match the minute
    containing ``observed_at``.  There is no daemon, catch-up, or implicit
    time-zone conversion; callers provide an aware UTC timestamp.
    """

    name = "scheduled"

    def detect(
        self,
        definitions: Iterable[ResearchAutomationDefinition],
        observed_at: datetime,
    ) -> tuple[AutomationTrigger, ...]:
        _require_utc(observed_at)
        due: list[AutomationTrigger] = []
        for definition in sorted(definitions, key=lambda item: (item.id, item.version)):
            if not definition.enabled or AutomationTriggerKind.SCHEDULED not in definition.trigger_kinds:
                continue
            if definition.schedule is None or not _cron_matches(definition.schedule, observed_at):
                continue
            as_of = observed_at.date()
            due.append(
                _trigger(
                    definition,
                    AutomationTriggerKind.SCHEDULED,
                    observed_at,
                    as_of,
                    (),
                    (),
                    f"scheduled:{definition.id}:{definition.version}:{observed_at:%Y-%m-%dT%H:%MZ}",
                    {"schedule": definition.schedule, "source": "scheduled"},
                )
            )
        return tuple(due)


class FilingTriggerSource:
    """Construct triggers from persisted filings visible at ``observed_at``."""

    name = "filing_available"

    def __init__(self, reader: PersistedFilingReader, tickers: Iterable[Ticker]) -> None:
        self._reader = reader
        self._tickers = tuple(sorted(set(tickers), key=lambda ticker: ticker.symbol))

    def detect(
        self,
        definitions: Iterable[ResearchAutomationDefinition],
        observed_at: datetime,
    ) -> tuple[AutomationTrigger, ...]:
        _require_utc(observed_at)
        available = self._available_filings(observed_at)
        triggers: list[AutomationTrigger] = []
        for definition in sorted(definitions, key=lambda item: (item.id, item.version)):
            if not definition.enabled or AutomationTriggerKind.FILING_AVAILABLE not in definition.trigger_kinds:
                continue
            for filing in available:
                reference = SourceReference("filing_document", filing.id)
                triggers.append(
                    _trigger(
                        definition,
                        AutomationTriggerKind.FILING_AVAILABLE,
                        observed_at,
                        filing.available_at.date(),
                        (reference,),
                        (filing.ticker,),
                        f"filing:{definition.id}:{definition.version}:{filing.id}",
                        {
                            "source": "persisted_filing",
                            "filing_id": filing.id,
                            "available_at": filing.available_at.isoformat(),
                        },
                    )
                )
        return tuple(triggers)

    def _available_filings(self, observed_at: datetime) -> tuple[FilingDocument, ...]:
        documents: dict[str, FilingDocument] = {}
        for ticker in self._tickers:
            for filing in self._reader.load_filings_available_on(ticker, observed_at.date()):
                if filing.ticker != ticker or filing.available_at > observed_at:
                    continue
                documents[filing.id] = filing
        return tuple(
            sorted(
                documents.values(),
                key=lambda filing: (filing.ticker.symbol, filing.available_at, filing.id),
            )
        )


def _trigger(
    definition: ResearchAutomationDefinition,
    kind: AutomationTriggerKind,
    occurred_at: datetime,
    as_of: date,
    references: tuple[SourceReference, ...],
    tickers: tuple[Ticker, ...],
    deduplication_key: str,
    metadata: dict[str, object],
) -> AutomationTrigger:
    _require_utc(occurred_at)
    trigger_id = f"trigger-{_digest(deduplication_key)}"
    return AutomationTrigger(
        trigger_id,
        kind,
        occurred_at,
        as_of,
        deduplication_key,
        references,
        tickers,
        {**metadata, "definition_id": definition.id, "definition_version": definition.version},
    )


def _validate_definition(
    definition: ResearchAutomationDefinition, kind: AutomationTriggerKind
) -> None:
    if not definition.enabled:
        raise ValueError("cannot build a trigger for a disabled automation")
    if kind not in definition.trigger_kinds:
        raise ValueError(f"automation does not accept {kind.value} triggers")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def _require_utc(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware UTC")
    if value.astimezone(timezone.utc) != value:
        raise ValueError("observed_at must be UTC")


def _cron_matches(expression: str, observed_at: datetime) -> bool:
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError("schedule must contain five UTC cron fields")
    cron_weekday = (observed_at.weekday() + 1) % 7
    values = (observed_at.minute, observed_at.hour, observed_at.day, observed_at.month, cron_weekday)
    bounds = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))
    return all(_field_matches(field, value, bound) for field, value, bound in zip(fields, values, bounds))


def _field_matches(field: str, value: int, bound: tuple[int, int]) -> bool:
    if not field:
        raise ValueError("schedule fields cannot be empty")
    allowed: set[int] = set()
    for part in field.split(","):
        if "-" in part:
            pieces = part.split("-")
            if len(pieces) != 2:
                raise ValueError("invalid schedule range")
            start, end = (_parse_schedule_int(piece, bound) for piece in pieces)
            if start > end:
                raise ValueError("schedule ranges must be ascending")
            allowed.update(range(start, end + 1))
        elif part == "*":
            allowed.update(range(bound[0], bound[1] + 1))
        else:
            allowed.add(_parse_schedule_int(part, bound))
    return value in allowed


def _parse_schedule_int(value: str, bound: tuple[int, int]) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError("schedule fields must contain integers") from exc
    if not bound[0] <= parsed <= bound[1]:
        raise ValueError("schedule value is outside its field bounds")
    return parsed
