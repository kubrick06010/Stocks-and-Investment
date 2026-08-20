from datetime import date, datetime, timezone

from stocks_investment.domain import (
    AnalysisStatus,
    FactorObservation,
    FactorScore,
    ResearchResult,
    ResearchRun,
    ResearchRunStatus,
    Ticker,
)
from stocks_investment.domain import CriterionResult, CriterionStatus
from stocks_investment.domain.research_intelligence import ThesisClassification
from stocks_investment.thesis import StructuredThesisEngine


def test_thesis_is_deterministic_and_lineage_preserving() -> None:
    run = ResearchRun(
        "r",
        datetime(2025, 1, 1, tzinfo=timezone.utc),
        date(2025, 1, 1),
        "s",
        "s_v1",
        "u",
        "u_v1",
        date(2025, 1, 1),
        {},
        status=ResearchRunStatus.COMPLETED,
    )
    obs = FactorObservation("quality", 90, AnalysisStatus.VALID, "score", run.as_of, "TTM", "q_v1")
    factor = FactorScore("quality", "q_v1", 90, AnalysisStatus.VALID, 1, (obs,), "strong")
    criterion = CriterionResult("pe", "g_v1", 20, 15, CriterionStatus.FAIL, False, "too high")
    result = ResearchResult(
        "r:AAA", "r", Ticker("AAA"), run.created_at, 1, 90, "selected", (factor,), (criterion,)
    )
    first, second = (
        StructuredThesisEngine().generate(run, result),
        StructuredThesisEngine().generate(run, result),
    )
    assert first == second
    assert first.classification is ThesisClassification.WATCH
    assert first.research_run_id == "r" and first.drivers[0].source_reference.entity_id == result.id
