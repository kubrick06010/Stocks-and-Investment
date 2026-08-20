"""A readable, deterministic multi-date factor/outcome population for Wave E."""

from __future__ import annotations

from datetime import date

from stocks_investment.domain import FactorOutcomeObservation, Ticker


RESEARCH_DATES = (
    date(2021, 3, 31),
    date(2021, 6, 30),
    date(2021, 9, 30),
    date(2021, 12, 31),
    date(2022, 3, 31),
    date(2022, 6, 30),
    date(2022, 9, 30),
    date(2022, 12, 31),
    date(2023, 3, 31),
    date(2023, 6, 30),
    date(2023, 9, 30),
    date(2023, 12, 31),
)
SYMBOLS = tuple(f"S{index:02d}" for index in range(12))


def quality_outcomes(*, horizon: str = "12M") -> tuple[FactorOutcomeObservation, ...]:
    """Return 144 stock-date observations with imperfect positive association.

    Scores vary cross-sectionally and through time. Returns include a stable
    score-related component, date regimes, and deterministic idiosyncratic
    noise, so the fixture proves machinery without manufacturing perfect IC.
    """

    rows: list[FactorOutcomeObservation] = []
    for date_index, as_of in enumerate(RESEARCH_DATES):
        regime = (0.02, -0.03, 0.01, 0.04)[date_index % 4]
        for symbol_index, symbol in enumerate(SYMBOLS):
            score = float(25 + ((symbol_index * 7 + date_index * 3) % 70))
            noise = ((symbol_index * 11 + date_index * 5) % 9 - 4) / 100.0
            excess = (score - 60.0) / 500.0 + regime + noise
            benchmark = 0.06 + (date_index % 3 - 1) * 0.01
            rows.append(
                FactorOutcomeObservation(
                    "quality",
                    "quality_v1",
                    f"research-{as_of.isoformat()}",
                    Ticker(symbol),
                    as_of,
                    score,
                    horizon,
                    benchmark + excess,
                    benchmark,
                    excess,
                    "valid",
                    "synthetic-large-cap-v1",
                    "SYNTH-BENCH",
                    "USD",
                    "quarterly",
                )
            )
    return tuple(rows)
