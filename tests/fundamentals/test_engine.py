from datetime import date
from datetime import datetime, timezone

from stocks_investment.fundamentals import (
    Fact,
    MarketSnapshot,
    MetricStatus,
    calculate_baseline,
    calculate_metric,
    fact_from_observation,
)
from stocks_investment.domain import DataProvenance, MetricObservation, MetricStatus as DomainMetricStatus, Period


AS_OF = date(2025, 12, 31)


def fact(
    name: str,
    value: float,
    end: date,
    kind: str = "quarter",
    *,
    available: date | None = None,
    units: str = "USD",
    currency: str | None = "USD",
) -> Fact:
    return Fact(name, value, date(end.year, end.month, 1), end, kind, units, currency, available)


def quarters(name: str, values: list[float], *, units: str = "USD") -> list[Fact]:
    ends = [date(2025, 3, 31), date(2025, 6, 30), date(2025, 9, 30), date(2025, 12, 31)]
    return [fact(name, value, end, units=units) for value, end in zip(values, ends)]


def test_ttm_requires_four_comparable_quarters_and_preserves_metadata() -> None:
    result = calculate_metric("ttm_revenue", quarters("revenue", [10, 20, 30, 40]), AS_OF)
    assert result.value == 100
    assert result.status is MetricStatus.VALID
    assert result.period == "TTM"
    assert result.units == "currency"
    assert result.version == "fundamentals-b1-v1"

    insufficient = calculate_metric("ttm_revenue", quarters("revenue", [10, 20, 30]), AS_OF)
    assert insufficient.status is MetricStatus.INSUFFICIENT_HISTORY
    assert insufficient.value is None


def test_as_of_filters_future_filings_and_zero_denominator_is_not_missing() -> None:
    revenue = fact("revenue", 100, date(2025, 9, 30), available=date(2026, 1, 10))
    assets = fact("current_assets", 100, date(2025, 9, 30))
    liabilities = fact("current_liabilities", 0, date(2025, 9, 30))
    assert calculate_metric("revenue", [revenue], AS_OF).status is MetricStatus.MISSING
    result = calculate_metric("current_ratio", [assets, liabilities], AS_OF)
    assert result.status is MetricStatus.ZERO_DENOMINATOR


def test_negative_equity_is_explicitly_not_meaningful() -> None:
    rows = [
        fact("total_debt", 50, date(2025, 12, 31), "annual"),
        fact("common_equity", -10, date(2025, 12, 31), "annual"),
    ]
    result = calculate_metric("debt_equity", rows, AS_OF)
    assert result.status is MetricStatus.NEGATIVE_NOT_MEANINGFUL


def test_free_cash_flow_normalizes_capex_sign_once() -> None:
    end = date(2025, 12, 31)
    rows = [
        fact("operating_cash_flow", 120, end, "annual"),
        fact("capital_expenditures", -30, end, "annual"),
    ]
    result = calculate_metric("levered_fcf", rows, AS_OF)
    assert result.value == 90
    assert result.notes == ("capex is normalized as a positive outflow",)


def test_baseline_contains_market_and_fundamental_outputs_without_scoring() -> None:
    rows = quarters("revenue", [100, 100, 100, 100]) + quarters("diluted_eps", [1, 1, 1, 1])
    end = date(2025, 12, 31)
    rows += [
        fact("current_assets", 200, end, "annual"),
        fact("current_liabilities", 100, end, "annual"),
        fact("total_debt", 50, end, "annual"),
        fact("common_equity", 150, end, "annual"),
    ]
    results = calculate_baseline(rows, AS_OF, MarketSnapshot(10, 20, AS_OF, "USD"))
    assert {result.name for result in results} >= {"market_cap", "ttm_revenue", "current_ratio"}
    assert all(not result.name.startswith("score") for result in results)


def annual_fact(name: str, value: float, *, end: date = date(2025, 3, 31)) -> Fact:
    return fact(name, value, end, "annual")


def test_enterprise_value_is_explicit_about_missing_optional_components() -> None:
    rows = [annual_fact("total_debt", 200), annual_fact("cash_and_equivalents", 50)]
    result = calculate_metric("enterprise_value", rows, AS_OF, MarketSnapshot(50, 100, AS_OF, "USD"))
    assert result.value == 5150
    assert result.status is MetricStatus.VALID
    assert "assumed zero" in " ".join(result.notes)


def test_enterprise_value_missing_required_cash_or_debt_is_missing() -> None:
    market = MarketSnapshot(50, 100, AS_OF, "USD")
    assert calculate_metric("enterprise_value", [annual_fact("total_debt", 0)], AS_OF, market).status is MetricStatus.MISSING
    assert calculate_metric("enterprise_value", [annual_fact("cash_and_equivalents", 0)], AS_OF, market).status is MetricStatus.MISSING


def test_enterprise_value_handles_zero_debt_cash_rich_and_negative_equity() -> None:
    market = MarketSnapshot(50, 100, AS_OF, "USD")
    cash_rich = [annual_fact("total_debt", 0), annual_fact("cash_and_equivalents", 600)]
    assert calculate_metric("enterprise_value", cash_rich, AS_OF, market).value == 4400
    high_debt = [annual_fact("total_debt", 5000), annual_fact("cash_and_equivalents", 10)]
    assert calculate_metric("enterprise_value", high_debt, AS_OF, market).value == 9990
    negative_equity = high_debt + [annual_fact("common_equity", -100)]
    assert calculate_metric("enterprise_value", negative_equity, AS_OF, market).value == 9990


def test_pe_pb_bvps_and_graham_have_economic_sign_guards() -> None:
    rows = [
        *quarters("diluted_eps", [1, 1, 1, 1]),
        annual_fact("common_equity", 1000),
    ]
    market = MarketSnapshot(50, 100, AS_OF, "USD")
    assert calculate_metric("pe_ttm", rows, AS_OF, market).value == 12.5
    assert calculate_metric("price_book", rows, AS_OF, market).value == 5
    assert calculate_metric("book_value_per_share", rows, AS_OF, market).value == 10
    assert calculate_metric("graham_number", rows, AS_OF, market).value == 30

    negative_eps = [*quarters("diluted_eps", [-2, -2, -2, -2]), annual_fact("common_equity", 1000)]
    assert calculate_metric("pe_ttm", negative_eps, AS_OF, market).status is MetricStatus.NOT_MEANINGFUL
    assert calculate_metric("graham_number", negative_eps, AS_OF, market).status is MetricStatus.NOT_MEANINGFUL
    negative_book = [*quarters("diluted_eps", [2, 2, 2, 2]), annual_fact("common_equity", -100)]
    assert calculate_metric("price_book", negative_book, AS_OF, market).status is MetricStatus.NOT_MEANINGFUL
    assert calculate_metric("graham_number", negative_book, AS_OF, market).status is MetricStatus.NOT_MEANINGFUL


def test_zero_and_missing_denominators_keep_distinct_semantics() -> None:
    market = MarketSnapshot(50, 100, AS_OF, "USD")
    zero_eps = [*quarters("diluted_eps", [0, 0, 0, 0]), annual_fact("common_equity", 100)]
    assert calculate_metric("pe_ttm", zero_eps, AS_OF, market).status is MetricStatus.NOT_MEANINGFUL
    zero_equity = [*quarters("diluted_eps", [1, 1, 1, 1]), annual_fact("common_equity", 0)]
    assert calculate_metric("price_book", zero_equity, AS_OF, market).status is MetricStatus.NOT_MEANINGFUL
    missing_equity = [*quarters("diluted_eps", [1, 1, 1, 1])]
    assert calculate_metric("price_book", missing_equity, AS_OF, market).status is MetricStatus.MISSING
    zero_assets = [annual_fact("current_assets", 0), annual_fact("current_liabilities", 100)]
    zero_ratio = calculate_metric("current_ratio", zero_assets, AS_OF)
    assert zero_ratio.status is MetricStatus.VALID
    assert zero_ratio.value == 0


def test_cross_formula_identities_hold_for_aligned_inputs() -> None:
    market = MarketSnapshot(50, 100, AS_OF, "USD")
    rows = [annual_fact("common_equity", 1000)]
    market_result = calculate_metric("market_cap", rows, AS_OF, market)
    bvps = calculate_metric("book_value_per_share", rows, AS_OF, market)
    pb = calculate_metric("price_book", rows, AS_OF, market)
    assert market_result.value == market.price * market.shares_outstanding
    assert bvps.value == 1000 / 100
    assert pb.value == market.price / bvps.value
    assert pb.value == market_result.value / 1000


def test_roic_standard_uses_average_beginning_and_ending_capital() -> None:
    rows = [annual_fact("nopat", 90), annual_fact("invested_capital_begin", 1000),
            annual_fact("invested_capital_end", 1200)]
    result = calculate_metric("roic_standard", rows, AS_OF)
    assert result.value == 90 / 1100 * 100
    assert result.version == "roic_nopat_avg_invested_capital_v1"
    simplified = calculate_metric("roic", [annual_fact("nopat", 90), annual_fact("invested_capital", 1000)], AS_OF)
    assert simplified.value == 9.0
    assert simplified.version == "roic_simplified_v1"


def test_fact_adapter_preserves_canonical_provenance() -> None:
    provenance = DataProvenance(
        source="sec:companyfacts",
        provider="sec-edgar",
        retrieved_at=datetime(2025, 5, 3, tzinfo=timezone.utc),
        effective_date=date(2025, 5, 2),
        available_at=datetime(2025, 5, 2, tzinfo=timezone.utc),
        filing_date=date(2025, 5, 2),
        period=Period(date(2025, 1, 1), date(2025, 3, 31), "quarter"),
        period_end=date(2025, 3, 31),
        currency="USD",
        units="USD",
        raw_identifier="accn/revenue",
    )
    observation = MetricObservation("revenue", 900, DomainMetricStatus.VALID, AS_OF, provenance)
    adapted = fact_from_observation(observation)
    result = calculate_metric("revenue", [adapted], AS_OF)
    assert adapted.provenance is provenance
    assert result.source_provenance == (provenance,)
