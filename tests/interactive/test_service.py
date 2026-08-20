from datetime import date

from stocks_investment.domain.interactive import (
    OutcomeVisibility, ResearchViewKind, ResearchViewRequest, ResearchViewStatus,
)
from stocks_investment.interactive.service import DeterministicInteractiveResearchService


class Reader:
    def __init__(self, snapshots=(), changes=(), entries=()):
        self.snapshots, self.changes, self.entries = snapshots, changes, entries
        self.calls = []

    def load_thesis_snapshots(self, ticker):
        self.calls.append(("snapshots", ticker.symbol))
        return self.snapshots

    def load_change_events(self, ticker):
        self.calls.append(("changes", ticker.symbol))
        return self.changes

    def load_watchlist_entries(self):
        self.calls.append(("watchlist",))
        return self.entries

    def load_monitoring_events(self, entry_id):
        return ()

    def load_research_outcomes(self, result_id):
        raise AssertionError("outcomes must not be read when excluded")


def test_missing_stock_is_explicit_and_provider_free():
    reader = Reader()
    service = DeterministicInteractiveResearchService(reader)
    view = service.query(ResearchViewRequest("q", ResearchViewKind.STOCK, service.version, "AAA"))
    assert view.status is ResearchViewStatus.NOT_FOUND
    assert view.report is None
    assert reader.calls == [("snapshots", "AAA")]


def test_methodology_mismatch_is_incompatible():
    service = DeterministicInteractiveResearchService(Reader())
    view = service.query(ResearchViewRequest("q", ResearchViewKind.WATCHLIST, "other"))
    assert view.status is ResearchViewStatus.INCOMPATIBLE
    assert view.report is not None


def test_exclude_outcomes_does_not_read_future_outcomes():
    service = DeterministicInteractiveResearchService(Reader())
    request = ResearchViewRequest(
        "q", ResearchViewKind.STOCK, service.version, "AAA",
        as_of=date(2024, 12, 31), outcome_visibility=OutcomeVisibility.EXCLUDE,
    )
    view = service.query(request)
    assert view.status is ResearchViewStatus.NOT_FOUND
