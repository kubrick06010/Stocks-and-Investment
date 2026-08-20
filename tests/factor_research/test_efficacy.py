from datetime import date
from dataclasses import replace

import pytest

from stocks_investment.domain import CohortIdentity, FactorOutcomeObservation, Ticker
from stocks_investment.factor_research import summarize_factor


def test_factor_efficacy_uses_persisted_scores_and_reports_coverage() -> None:
    rows = tuple(
        FactorOutcomeObservation(
            "quality",
            "quality_v1",
            f"r{i}",
            Ticker(f"A{i}"),
            date(2025, 1, 1),
            float(i),
            "12M",
            0.1 * i,
            0.02,
            0.1 * i - 0.02,
            "measured",
            "synthetic",
            "SYNTH",
            "USD",
            "quarterly",
        )
        for i in range(1, 6)
    )
    cohort = CohortIdentity(
        "quality_v1",
        "synthetic",
        date(2025, 1, 1),
        date(2025, 1, 1),
        "12M",
        "quarterly",
        "USD",
        "SYNTH",
    )
    summary = summarize_factor(rows, cohort)
    assert summary.sample_size == 5
    assert summary.coverage == 1
    assert summary.spread is not None and summary.rank_ic is not None


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("factor_version", "quality_v2"),
        ("universe", "NASDAQ"),
        ("benchmark", "OTHER"),
        ("horizon", "3M"),
        ("base_currency", "EUR"),
        ("rebalance_cadence", "monthly"),
    ),
)
def test_factor_efficacy_rejects_mixed_cohort_identity(field: str, value: str) -> None:
    row = FactorOutcomeObservation(
        "quality", "quality_v1", "r1", Ticker("AAA"), date(2025, 1, 1), 80,
        "12M", .1, .02, .08, "measured", "synthetic", "SYNTH", "USD", "quarterly",
    )
    cohort = CohortIdentity(
        "quality_v1", "synthetic", date(2025, 1, 1), date(2025, 1, 1),
        "12M", "quarterly", "USD", "SYNTH",
    )
    with pytest.raises(ValueError, match="cohort"):
        summarize_factor((row, replace(row, **{field: value})), cohort)
