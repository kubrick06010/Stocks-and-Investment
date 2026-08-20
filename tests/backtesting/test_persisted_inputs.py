from datetime import datetime, timezone

from stocks_investment.backtesting.engine import scores_from_persisted_results
from stocks_investment.domain import ResearchResult, Ticker


def test_backtest_can_consume_frozen_research_results() -> None:
    result = ResearchResult("r:AAA", "r", Ticker("AAA"), datetime(2025, 1, 1, tzinfo=timezone.utc), 1, 88.0, "selected")
    assert scores_from_persisted_results((result,)) == {"AAA": 88.0}
