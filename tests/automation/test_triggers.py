from datetime import date, datetime, timezone

import pytest

from stocks_investment.automation.triggers import (
    FilingTriggerSource,
    ScheduledTriggerSource,
    build_manual_trigger,
)
from stocks_investment.domain import (
    AutomationTriggerKind,
    DataProvenance,
    FilingDocument,
    FilingForm,
    ResearchAutomationDefinition,
    RetryPolicy,
    Ticker,
)


UTC = timezone.utc
OBSERVED = datetime(2026, 8, 19, 8, 0, tzinfo=UTC)


def _definition(*kinds: AutomationTriggerKind, schedule: str | None = None, enabled: bool = True):
    return ResearchAutomationDefinition(
        "job", "job_v1", "pipeline_v1", kinds, "strategy", "strategy_v1", "universe",
        schedule, RetryPolicy(1, 0, 0, ()), enabled, OBSERVED,
    )


def _filing(identifier: str, symbol: str, available: datetime) -> FilingDocument:
    provenance = DataProvenance(
        "sec", "fixture", available, available.date(), available_at=available,
        filing_date=available.date(), period_end=date(2026, 6, 30),
    )
    return FilingDocument(
        identifier, Ticker(symbol), "1", identifier, FilingForm.FORM_10_Q,
        available, available, date(2026, 6, 30), "doc.htm", f"https://example/{identifier}",
        identifier, available, "text/html", 10, provenance,
    )


class _Reader:
    def __init__(self, filings: tuple[FilingDocument, ...]) -> None:
        self.filings = filings
        self.calls: list[tuple[Ticker, date]] = []

    def load_filings_available_on(self, ticker: Ticker, as_of: date) -> tuple[FilingDocument, ...]:
        self.calls.append((ticker, as_of))
        return tuple(filing for filing in self.filings if filing.ticker == ticker)


def test_manual_trigger_is_replayable_and_uses_injected_observation() -> None:
    definition = _definition(AutomationTriggerKind.MANUAL)
    first = build_manual_trigger(definition, as_of=date(2026, 8, 18), observed_at=OBSERVED)
    second = build_manual_trigger(definition, as_of=date(2026, 8, 18), observed_at=OBSERVED)
    assert first == second
    assert first.kind is AutomationTriggerKind.MANUAL
    assert first.metadata["source"] == "manual"


def test_manual_trigger_rejects_disabled_or_unsupported_definition() -> None:
    with pytest.raises(ValueError, match="disabled"):
        build_manual_trigger(_definition(AutomationTriggerKind.MANUAL, enabled=False), as_of=OBSERVED.date(), observed_at=OBSERVED)
    with pytest.raises(ValueError, match="does not accept"):
        build_manual_trigger(_definition(AutomationTriggerKind.SCHEDULED, schedule="0 8 * * *"), as_of=OBSERVED.date(), observed_at=OBSERVED)


def test_scheduled_source_matches_due_utc_minute_and_is_sorted() -> None:
    due = _definition(AutomationTriggerKind.SCHEDULED, schedule="0 8 * * 3")
    not_due = _definition(AutomationTriggerKind.SCHEDULED, schedule="30 8 * * 3")
    source = ScheduledTriggerSource()
    triggers = source.detect((not_due, due), OBSERVED)
    assert len(triggers) == 1
    assert triggers[0].deduplication_key.endswith("2026-08-19T08:00Z")


def test_scheduled_source_rejects_naive_and_invalid_schedule() -> None:
    with pytest.raises(ValueError, match="UTC"):
        ScheduledTriggerSource().detect((), datetime(2026, 8, 19, 8))
    invalid = _definition(AutomationTriggerKind.SCHEDULED, schedule="bad")
    with pytest.raises(ValueError, match="five"):
        ScheduledTriggerSource().detect((invalid,), OBSERVED)


def test_filing_source_reads_persisted_documents_only_and_excludes_future() -> None:
    visible_a = _filing("b", "BBB", datetime(2026, 8, 19, 7, 59, tzinfo=UTC))
    visible_b = _filing("a", "AAA", datetime(2026, 8, 19, 8, 0, tzinfo=UTC))
    future = _filing("future", "CCC", datetime(2026, 8, 19, 8, 1, tzinfo=UTC))
    reader = _Reader((visible_a, future, visible_b))
    triggers = FilingTriggerSource(reader, (Ticker("CCC"), Ticker("BBB"), Ticker("AAA"))).detect(
        (_definition(AutomationTriggerKind.FILING_AVAILABLE),), OBSERVED
    )
    assert len(triggers) == 2
    assert tuple(trigger.tickers for trigger in triggers) == ((Ticker("AAA"),), (Ticker("BBB"),))
    assert tuple(trigger.source_references[0].entity_id for trigger in triggers) == ("a", "b")
    assert future.id not in {
        trigger.source_references[0].entity_id for trigger in triggers
    }
    assert all(call[0].symbol in {"AAA", "BBB", "CCC"} for call in reader.calls)


def test_filing_replay_is_stable_and_empty_persisted_set_has_no_trigger() -> None:
    filing = _filing("a", "AAA", datetime(2026, 8, 19, 7, 0, tzinfo=UTC))
    definition = _definition(AutomationTriggerKind.FILING_AVAILABLE)
    source = FilingTriggerSource(_Reader((filing,)), (Ticker("AAA"),))
    first = source.detect((definition,), OBSERVED)
    second = source.detect((definition,), OBSERVED)
    assert first == second
    assert FilingTriggerSource(_Reader(()), (Ticker("AAA"),)).detect((definition,), OBSERVED) == ()


def test_filing_source_rejects_non_utc_observed_time() -> None:
    with pytest.raises(ValueError, match="UTC"):
        FilingTriggerSource(_Reader(()), (Ticker("AAA"),)).detect(
            (_definition(AutomationTriggerKind.FILING_AVAILABLE),), datetime(2026, 8, 19, 8, 0)
        )


def test_old_filing_keeps_same_identity_when_a_new_filing_arrives() -> None:
    old = _filing("old", "AAA", datetime(2026, 8, 18, 7, tzinfo=UTC))
    new = _filing("new", "AAA", datetime(2026, 8, 19, 7, tzinfo=UTC))
    definition = _definition(AutomationTriggerKind.FILING_AVAILABLE)
    old_only = FilingTriggerSource(_Reader((old,)), (Ticker("AAA"),)).detect(
        (definition,), OBSERVED
    )
    with_new = FilingTriggerSource(_Reader((new, old)), (Ticker("AAA"),)).detect(
        (definition,), OBSERVED
    )
    assert old_only[0] == with_new[0]
    assert with_new[1].source_references[0].entity_id == "new"
