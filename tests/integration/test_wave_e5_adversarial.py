"""Independent E5 attacks against the local historical inspection boundary."""

from datetime import date
import sqlite3

import pytest

from stocks_investment.domain import (
    FactorOutcomeObservation,
    OutcomeVisibility,
    ResearchOutcome,
    ResearchViewKind,
    ResearchViewStatus,
    Ticker,
)
from stocks_investment.interactive import DeterministicInteractiveResearchService, render_research_view
from stocks_investment.storage import ReadOnlySQLiteStorage, SQLiteStorage
from tests.e2e.test_wave_e5_interactive_research import T0, _populate, _request


def test_future_outcome_attack_cannot_change_t0_research_view(tmp_path) -> None:
    path = tmp_path / "future-attack.db"
    _populate(path)
    with ReadOnlySQLiteStorage(path) as reader:
        service = DeterministicInteractiveResearchService(reader)
        request = _request(ResearchViewKind.STOCK, "AAA", as_of=T0)
        before = render_research_view(service.query(request), "json")

    with SQLiteStorage(path) as writer:
        writer.save_research_outcome(ResearchOutcome("run-t0:AAA", date(2025, 3, 31), "12M", 500.0, .01, 499.99))

    with ReadOnlySQLiteStorage(path) as reader:
        service = DeterministicInteractiveResearchService(reader)
        after = render_research_view(service.query(request), "json")
        post_hoc = render_research_view(service.query(_request(
            ResearchViewKind.STOCK, "AAA", as_of=T0,
            outcome_visibility=OutcomeVisibility.SEPARATE,
        )), "json")
    assert before == after
    assert "500.0" in post_hoc
    assert "500.0" not in before


def test_mixed_factor_cohort_is_not_silently_aggregated(tmp_path) -> None:
    path = tmp_path / "cohort-attack.db"
    _populate(path)
    with SQLiteStorage(path) as writer:
        writer.save_factor_outcome_observation(FactorOutcomeObservation(
            "quality", "quality_v1", "mixed-run", Ticker("MIXED"), T0, 99,
            "12M", .2, .01, .19, "measured", "other-universe", "BENCH", "USD", "quarterly",
        ))
    with ReadOnlySQLiteStorage(path) as reader:
        view = DeterministicInteractiveResearchService(reader).query(_request(
            ResearchViewKind.FACTOR_EFFICACY, "quality",
            factor_version="quality_v1", horizon="12M",
        ))
    assert view.status is ResearchViewStatus.INCOMPATIBLE
    assert "incompatible" in " ".join(view.warnings)


def test_read_only_interface_has_no_network_fallback_or_write_path(tmp_path, monkeypatch) -> None:
    path = tmp_path / "readonly-attack.db"
    _populate(path)
    before = path.read_bytes()

    def fail(*_args, **_kwargs):
        raise AssertionError("network/provider fallback is forbidden")

    monkeypatch.setattr("socket.create_connection", fail)
    with ReadOnlySQLiteStorage(path) as reader:
        service = DeterministicInteractiveResearchService(reader)
        view = service.query(_request(ResearchViewKind.THESIS_HISTORY, "AAA"))
        assert view.status is ResearchViewStatus.VALID
        with pytest.raises(sqlite3.OperationalError):  # SQLite query_only rejects inherited writes.
            reader.save_research_outcome(ResearchOutcome("run-t0:AAA", T0, "1M", .1, .1, 0))
    assert path.read_bytes() == before
