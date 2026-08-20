"""Compatibility snapshot API for the B1 baseline metrics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import sqrt

from stocks_investment.domain import DataProvenance, MetricStatus, Period


@dataclass(frozen=True, slots=True)
class MetricValue:
    name: str
    value: float | None
    status: MetricStatus
    as_of: date
    provenance: DataProvenance
    units: str
    currency: str | None
    period: Period | None
    source_inputs: tuple[str, ...] = ()
    calculation_version: str = "fundamentals-b1-v1"
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class FundamentalInputs:
    as_of: date
    provenance: DataProvenance
    currency: str
    price: float | None = None
    shares_outstanding: float | None = None
    diluted_eps_ttm: float | None = None
    revenue_ttm: float | None = None
    revenue_prior: float | None = None
    gross_profit_ttm: float | None = None
    operating_income_ttm: float | None = None
    book_value: float | None = None
    debt: float | None = None
    cash: float | None = None
    total_liabilities: float | None = None
    ebitda_ttm: float | None = None
    fcf_ttm: float | None = None
    fcf_prior: float | None = None
    operating_cash_flow_ttm: float | None = None
    capex_ttm: float | None = None
    current_assets: float | None = None
    current_liabilities: float | None = None
    quick_assets: float | None = None
    total_assets: float | None = None
    net_income_ttm: float | None = None
    interest_expense_ttm: float | None = None
    common_equity: float | None = None
    nopat_ttm: float | None = None
    invested_capital: float | None = None
    eps_prior: float | None = None
    period: Period | None = None


def _m(
    name: str,
    x: FundamentalInputs,
    value: float | None,
    status: MetricStatus,
    units: str,
    fields: tuple[str, ...],
    note: str | None = None,
) -> MetricValue:
    return MetricValue(
        name,
        value if status is MetricStatus.VALID else None,
        status,
        x.as_of,
        x.provenance,
        units,
        x.currency,
        x.period,
        fields,
        notes=note,
    )


def _ratio(
    name: str,
    a: float | None,
    b: float | None,
    x: FundamentalInputs,
    units: str = "ratio",
    positive: bool = False,
    fields: tuple[str, ...] = ("numerator", "denominator"),
) -> MetricValue:
    if a is None or b is None:
        return _m(name, x, None, MetricStatus.MISSING, units, fields)
    if b == 0:
        return _m(name, x, None, MetricStatus.NOT_MEANINGFUL, units, fields, "zero denominator")
    if positive and b < 0:
        return _m(name, x, None, MetricStatus.NOT_MEANINGFUL, units, fields, "negative denominator")
    return _m(name, x, a / b, MetricStatus.VALID, units, fields)


def calculate_baseline_metrics(x: FundamentalInputs) -> tuple[MetricValue, ...]:
    """Calculate valuation, health, profitability, cash-flow, and growth metrics."""
    money, multiple = x.currency, "multiple"
    market = _m(
        "market_cap",
        x,
        x.price * x.shares_outstanding
        if x.price is not None and x.shares_outstanding is not None
        else None,
        MetricStatus.VALID
        if x.price is not None and x.shares_outstanding is not None
        else MetricStatus.MISSING,
        money,
        ("price", "shares_outstanding"),
    )
    ev = _m(
        "enterprise_value",
        x,
        market.value + x.debt - x.cash
        if market.value is not None and x.debt is not None and x.cash is not None
        else None,
        MetricStatus.VALID
        if market.value is not None and x.debt is not None and x.cash is not None
        else MetricStatus.MISSING,
        money,
        ("market_cap", "debt", "cash"),
    )
    bvps = _ratio(
        "book_value_per_share",
        x.book_value,
        x.shares_outstanding,
        x,
        f"{money}/share",
        True,
        ("book_value", "shares_outstanding"),
    )
    pe = _ratio(
        "price_to_earnings",
        x.price,
        x.diluted_eps_ttm,
        x,
        multiple,
        True,
        ("price", "diluted_eps_ttm"),
    )
    values = [
        market,
        ev,
        bvps,
        pe,
        _ratio("price_to_book", x.price, bvps.value, x, multiple, True),
        _ratio(
            "price_to_sales",
            x.price,
            x.revenue_ttm / x.shares_outstanding
            if x.revenue_ttm is not None and x.shares_outstanding
            else None,
            x,
            multiple,
        ),
        _ratio("ev_to_revenue", ev.value, x.revenue_ttm, x, multiple, True),
        _ratio("ev_to_ebitda", ev.value, x.ebitda_ttm, x, multiple, True),
        _ratio("fcf_yield", x.fcf_ttm, market.value, x, "fraction"),
        _ratio("earnings_yield", x.diluted_eps_ttm, x.price, x, "fraction"),
        _m(
            "book_value",
            x,
            x.book_value,
            MetricStatus.VALID if x.book_value is not None else MetricStatus.MISSING,
            money,
            ("book_value",),
        ),
        _ratio("current_ratio", x.current_assets, x.current_liabilities, x, "ratio"),
        _ratio("quick_ratio", x.quick_assets, x.current_liabilities, x),
        _ratio("debt_to_equity", x.debt, x.common_equity, x, positive=True),
        _m(
            "net_debt",
            x,
            x.debt - x.cash if x.debt is not None and x.cash is not None else None,
            MetricStatus.VALID
            if x.debt is not None and x.cash is not None
            else MetricStatus.MISSING,
            money,
            ("debt", "cash"),
        ),
        _ratio("gross_margin", x.gross_profit_ttm, x.revenue_ttm, x, "fraction"),
        _ratio("operating_margin", x.operating_income_ttm, x.revenue_ttm, x, "fraction"),
        _ratio("net_margin", x.net_income_ttm, x.revenue_ttm, x, "fraction"),
        _ratio("roa", x.net_income_ttm, x.total_assets, x, "fraction", True),
        _ratio("roe", x.net_income_ttm, x.common_equity, x, "fraction", True),
        _ratio("roic", x.nopat_ttm, x.invested_capital, x, "fraction", True),
        _m(
            "free_cash_flow",
            x,
            x.fcf_ttm,
            MetricStatus.VALID if x.fcf_ttm is not None else MetricStatus.MISSING,
            money,
            ("operating_cash_flow_ttm", "capex_ttm"),
        ),
        _ratio(
            "revenue_yoy",
            x.revenue_ttm - x.revenue_prior
            if x.revenue_ttm is not None and x.revenue_prior is not None
            else None,
            x.revenue_prior,
            x,
            "fraction",
            True,
        ),
        _ratio(
            "eps_yoy",
            x.diluted_eps_ttm - x.eps_prior
            if x.diluted_eps_ttm is not None and x.eps_prior is not None
            else None,
            x.eps_prior,
            x,
            "fraction",
            True,
        ),
    ]
    graham = (
        sqrt(22.5 * x.diluted_eps_ttm * bvps.value)
        if x.diluted_eps_ttm is not None
        and bvps.value is not None
        and x.diluted_eps_ttm > 0
        and bvps.value > 0
        else None
    )
    values.append(
        _m(
            "graham_number",
            x,
            graham,
            MetricStatus.VALID if graham is not None else MetricStatus.NOT_MEANINGFUL,
            f"{money}/share",
            ("diluted_eps_ttm", "book_value", "shares_outstanding"),
        )
    )
    return tuple(values)
