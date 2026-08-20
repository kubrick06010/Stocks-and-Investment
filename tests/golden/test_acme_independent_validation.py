import json
import math
from datetime import date
from pathlib import Path

from stocks_investment.fundamentals import Fact, MarketSnapshot, MetricStatus, calculate_metric


FIXTURE = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "financial" / "acme_2025.json").read_text()
)
INPUTS = FIXTURE["inputs"]
EXPECTED = FIXTURE["expected"]
AS_OF = date.fromisoformat(FIXTURE["as_of"])
PERIOD_END = date.fromisoformat(FIXTURE["period_end"])


def fact(name: str, value: float) -> Fact:
    return Fact(name, value, date(2025, 1, 1), PERIOD_END, "quarter", "USD", "USD", AS_OF)


def test_independent_hand_calculations_are_stable() -> None:
    market_cap = INPUTS["price"] * INPUTS["shares_outstanding"]
    enterprise_value = market_cap + INPUTS["debt"] - INPUTS["cash"]
    book_value_per_share = INPUTS["book_value"] / INPUTS["shares_outstanding"]
    fcf = INPUTS["operating_cash_flow"] - INPUTS["capital_expenditures"]
    assert market_cap == EXPECTED["market_cap"]
    assert enterprise_value == EXPECTED["enterprise_value"]
    assert book_value_per_share == EXPECTED["book_value_per_share"]
    assert fcf == EXPECTED["fcf"]
    assert math.isclose(INPUTS["nopat"] / INPUTS["invested_capital"], EXPECTED["roic"])
    assert INPUTS["book_value"] == EXPECTED["book_value"]


def test_production_engine_agrees_on_supported_golden_metrics() -> None:
    rows = [
        fact("revenue", INPUTS["revenue"]),
        fact("revenue", INPUTS["revenue_prior"]),
        fact("diluted_eps", INPUTS["eps"]),
        fact("current_assets", INPUTS["current_assets"]),
        fact("current_liabilities", INPUTS["current_liabilities"]),
        fact("total_debt", INPUTS["debt"]),
        fact("common_equity", INPUTS["common_equity"]),
        fact("operating_cash_flow", INPUTS["operating_cash_flow"]),
        fact("capital_expenditures", -INPUTS["capital_expenditures"]),
    ]
    market = MarketSnapshot(INPUTS["price"], INPUTS["shares_outstanding"], AS_OF, "USD")
    assert calculate_metric("market_cap", rows, AS_OF, market).value == EXPECTED["market_cap"]
    assert calculate_metric("current_ratio", rows, AS_OF).value == EXPECTED["current_ratio"]
    assert calculate_metric("debt_equity", rows, AS_OF).value == INPUTS["debt"] / INPUTS["common_equity"]
    assert calculate_metric("levered_fcf", rows, AS_OF).value == EXPECTED["fcf"]


def _quarterly(name: str, values: list[float]) -> list[Fact]:
    ends = [date(2024, 6, 30), date(2024, 9, 30), date(2024, 12, 31), date(2025, 3, 31)]
    return [Fact(name, value, date(end.year, end.month, 1), end, "quarter", "USD", "USD", AS_OF)
            for value, end in zip(values, ends)]


def test_new_metrics_match_independent_hand_derivations() -> None:
    rows = _quarterly("diluted_eps", [1, 1, 1, 1]) + [
        fact("common_equity", INPUTS["book_value"]),
        fact("total_debt", INPUTS["debt"]),
        fact("cash_and_equivalents", INPUTS["cash"]),
        fact("nopat", INPUTS["nopat"]),
        Fact("invested_capital_begin", 1100, date(2024, 1, 1), date(2024, 12, 31), "annual", "USD", "USD", AS_OF),
        Fact("invested_capital_end", INPUTS["invested_capital"], date(2025, 1, 1), date(2025, 3, 31), "quarter", "USD", "USD", AS_OF),
    ]
    market = MarketSnapshot(INPUTS["price"], INPUTS["shares_outstanding"], AS_OF, "USD")
    assert calculate_metric("enterprise_value", rows, AS_OF, market).value == EXPECTED["enterprise_value"]
    assert calculate_metric("pe_ttm", rows, AS_OF, market).value == EXPECTED["pe"]
    assert calculate_metric("price_book", rows, AS_OF, market).value == EXPECTED["pb"]
    assert calculate_metric("book_value", rows, AS_OF).value == EXPECTED["book_value"]
    assert calculate_metric("book_value_per_share", rows, AS_OF, market).value == EXPECTED["book_value_per_share"]
    assert calculate_metric("graham_number", rows, AS_OF, market).value == EXPECTED["graham_number"]
    assert math.isclose(calculate_metric("roic_standard", rows, AS_OF).value, EXPECTED["roic_standard"] * 100)


def test_golden_missing_inputs_are_not_falsely_treated_as_zero() -> None:
    rows = [fact("diluted_eps", INPUTS["eps"])]
    result = calculate_metric("price_book", rows, AS_OF)
    assert result.status is MetricStatus.MISSING


def test_lossmaking_fixture_preserves_negative_values_without_coercion() -> None:
    loss = json.loads(
        (Path(__file__).parents[1] / "fixtures" / "financial" / "lossmaking_2025.json").read_text()
    )
    values = loss["inputs"]
    assert values["price"] * values["shares_outstanding"] == loss["expected"]["market_cap"]
    assert values["operating_cash_flow"] - values["capital_expenditures"] == loss["expected"]["fcf"]
    assert values["book_value"] / values["shares_outstanding"] == loss["expected"]["book_value_per_share"]


def test_graham_trap_negative_eps_and_negative_bvps_is_not_valid() -> None:
    rows = _quarterly("diluted_eps", [-2, -2, -2, -2]) + [
        fact("common_equity", -250)
    ]
    result = calculate_metric("graham_number", rows, AS_OF, MarketSnapshot(20, 50, AS_OF, "USD"))
    assert result.status is MetricStatus.NOT_MEANINGFUL
    assert result.value is None
