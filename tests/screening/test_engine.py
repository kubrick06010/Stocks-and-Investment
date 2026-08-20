from datetime import date, datetime, timezone

from stocks_investment.domain import (
    AnalysisStatus,
    CompositeScore,
    FactorObservation,
    FactorScore,
    MissingDataPolicy,
    Ticker,
    UniverseSnapshot,
)
from stocks_investment.screening import Candidate, ScreeningEngine
from stocks_investment.storage import SQLiteStorage


AS_OF = date(2025, 5, 3)


class MemoryResearchStorage:
    def __init__(self) -> None:
        self.runs = []
        self.results = []

    def save_research_run(self, run):
        self.runs.append(run)

    def save_research_result(self, result):
        self.results.append(result)

    def save_observation(self, ticker, observation):
        raise AssertionError("screening must not duplicate observation storage")

    def load_observations(self, ticker, as_of):
        return ()

    def attach_observation(self, result_id, observation_id):
        raise AssertionError("factor observations have no shared storage IDs")


def universe() -> UniverseSnapshot:
    return UniverseSnapshot("fixture", "fixture-v3", AS_OF, (Ticker("AAA"), Ticker("BBB"), Ticker("CCC")), "test")


def score(ticker: str, value: float | None, policy: MissingDataPolicy = MissingDataPolicy.FAIL) -> CompositeScore:
    observation = FactorObservation(
        "value", 1.0, AnalysisStatus.VALID, "multiple", AS_OF, "TTM", "value-v1"
    )
    component = FactorScore(
        "value", "value-v1", value, AnalysisStatus.VALID if value is not None else AnalysisStatus.MISSING,
        1.0, (observation,), "fixture score"
    )
    return CompositeScore("fixture", "fixture-v1", (component,), {"value": 1.0}, policy, value, component.status, AS_OF)


def test_filters_and_ranking_are_deterministic_and_keep_missing_distinct() -> None:
    storage = MemoryResearchStorage()
    engine = ScreeningEngine(storage)
    candidates = {
        "AAA": Candidate(Ticker("AAA"), score("AAA", 80.0)),
        "BBB": Candidate(Ticker("BBB"), score("BBB", None)),
        "CCC": Candidate(Ticker("CCC"), score("CCC", 80.0)),
    }
    result = engine.run(
        universe(), candidates, strategy_name="fixture", strategy_version="v1",
        filters=(lambda ticker, observations: ticker.symbol != "CCC",),
        created_at=datetime(2025, 5, 3, tzinfo=timezone.utc),
    )

    assert [(item.ticker.symbol, item.rank, item.status) for item in result.selections] == [
        ("AAA", 1, "selected"), ("BBB", None, "insufficient_data"), ("CCC", None, "filtered")
    ]
    assert result.run.parameters["universe_version"] == "fixture-v3"
    assert result.run.parameters["missing_data_policy"] == "insufficient_data"
    assert storage.runs[0] == result.run
    assert [item.ticker.symbol for item in storage.results] == ["AAA", "BBB", "CCC"]


def test_run_id_is_reproducible_and_universe_version_changes_identity() -> None:
    kwargs = dict(
        strategy_name="fixture", strategy_version="v1", persist=False,
        created_at=datetime(2025, 5, 3, tzinfo=timezone.utc),
    )
    candidates = [Candidate(Ticker("AAA"), score("AAA", 10.0))]
    first = ScreeningEngine().run(universe(), candidates, **kwargs)
    second = ScreeningEngine().run(universe(), candidates, **kwargs)
    changed = UniverseSnapshot("fixture", "fixture-v4", AS_OF, (Ticker("AAA"),), "test")
    third = ScreeningEngine().run(changed, candidates, **kwargs)
    assert first.run.id == second.run.id
    assert first.run.id != third.run.id


def test_boolean_filter_is_adapted_without_shared_contract_changes() -> None:
    result = ScreeningEngine().run(
        universe(), [Candidate(Ticker("AAA"), score("AAA", 50.0))],
        strategy_name="fixture", strategy_version="v1", persist=False,
        filters=(lambda ticker, observations: True,),
    )
    assert result.selections[0].criteria[0].passed is True
    assert result.selections[0].criteria[0].criterion_version == "callable_v1"


def test_existing_sqlite_backend_round_trips_run_and_results(tmp_path) -> None:
    with SQLiteStorage(tmp_path / "research.sqlite") as storage:
        result = ScreeningEngine(storage).run(
            universe(), [Candidate(Ticker("AAA"), score("AAA", 50.0))],
            strategy_name="fixture", strategy_version="v1", data_snapshot="snapshot-1",
            persist=True, created_at=datetime(2025, 5, 3, tzinfo=timezone.utc),
        )
        restored_run = storage.load_research_run(result.run.id)
        restored_result = storage.load_research_result(f"{result.run.id}:AAA")

    assert restored_run is not None
    assert restored_run.parameters["universe_version"] == "fixture-v3"
    assert restored_run.data_snapshot == "snapshot-1"
    assert restored_result is not None
    assert (restored_result.rank, restored_result.composite_score) == (1, 50.0)
