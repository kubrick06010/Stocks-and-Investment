"""Provider-neutral fundamental calculations.

The engine accepts already-normalized facts. It deliberately has no provider,
storage, clock, logging, or global mutable state dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum
from math import isfinite
from typing import Iterable, Mapping

from stocks_investment.domain.models import DataProvenance, MetricObservation

CALCULATION_VERSION = "fundamentals-b1-v1"


class MetricStatus(StrEnum):
    VALID = "valid"
    MISSING = "missing"
    ZERO_DENOMINATOR = "zero_denominator"
    NEGATIVE_NOT_MEANINGFUL = "negative_not_meaningful"
    NOT_MEANINGFUL = "not_meaningful"
    NOT_APPLICABLE = "not_applicable"
    STALE = "stale"
    INSUFFICIENT_HISTORY = "insufficient_history"
    PERIOD_MISMATCH = "period_mismatch"


@dataclass(frozen=True, slots=True)
class Fact:
    """A normalized scalar with its accounting period and availability date."""

    name: str
    value: float | None
    period_start: date
    period_end: date
    period_kind: str
    units: str
    currency: str | None = None
    available_at: date | None = None
    source: str = "normalized"
    provenance: DataProvenance | None = None


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    price: float | None
    shares_outstanding: float | None
    as_of: date
    currency: str
    share_basis: str = "ending"
    provenance: DataProvenance | None = None


@dataclass(frozen=True, slots=True)
class MetricResult:
    """A structured calculation result; invalid results never carry a value."""

    name: str
    value: float | None
    status: MetricStatus
    as_of: date
    period: str
    units: str
    currency: str | None
    inputs: tuple[str, ...]
    version: str = CALCULATION_VERSION
    notes: tuple[str, ...] = ()
    source_provenance: tuple[DataProvenance, ...] = ()


def _result(
    name: str,
    value: float | None,
    status: MetricStatus,
    as_of: date,
    period: str,
    units: str,
    currency: str | None,
    inputs: Iterable[str],
    *notes: str,
    version: str = CALCULATION_VERSION,
) -> MetricResult:
    if status is MetricStatus.VALID and (value is None or not isfinite(value)):
        raise ValueError("valid results require a finite value")
    if status is not MetricStatus.VALID:
        value = None
    return MetricResult(
        name, value, status, as_of, period, units, currency, tuple(inputs),
        version=version, notes=tuple(notes)
    )


def _facts(raw: Mapping[str, Fact] | Iterable[Fact]) -> tuple[Fact, ...]:
    return tuple(raw.values()) if isinstance(raw, Mapping) else tuple(raw)


def _eligible(facts: tuple[Fact, ...], name: str, as_of: date) -> tuple[Fact, ...]:
    return tuple(
        f for f in facts if f.name == name and (f.available_at is None or f.available_at <= as_of)
    )


def _latest(facts: tuple[Fact, ...], name: str, as_of: date) -> Fact | None:
    eligible = [f for f in _eligible(facts, name, as_of) if f.period_end <= as_of]
    return max(eligible, key=lambda f: f.period_end, default=None)


def _missing(name: str, as_of: date, units: str = "ratio", *inputs: str) -> MetricResult:
    return _result(name, None, MetricStatus.MISSING, as_of, "unknown", units, None, inputs)


def _divide(
    name: str,
    numerator: Fact,
    denominator: Fact,
    as_of: date,
    units: str,
    *,
    negative_denominator: bool = False,
) -> MetricResult:
    inputs = (numerator.name, denominator.name)
    if numerator.value is None or denominator.value is None:
        return _result(
            name,
            None,
            MetricStatus.MISSING,
            as_of,
            numerator.period_kind,
            units,
            numerator.currency,
            inputs,
        )
    if (
        numerator.period_end != denominator.period_end
        or numerator.period_start != denominator.period_start
    ):
        return _result(
            name,
            None,
            MetricStatus.PERIOD_MISMATCH,
            as_of,
            numerator.period_kind,
            units,
            numerator.currency,
            inputs,
        )
    if denominator.value == 0:
        return _result(
            name,
            None,
            MetricStatus.ZERO_DENOMINATOR,
            as_of,
            numerator.period_kind,
            units,
            numerator.currency,
            inputs,
        )
    if negative_denominator and denominator.value < 0:
        return _result(
            name,
            None,
            MetricStatus.NEGATIVE_NOT_MEANINGFUL,
            as_of,
            numerator.period_kind,
            units,
            numerator.currency,
            inputs,
        )
    return _result(
        name,
        numerator.value / denominator.value,
        MetricStatus.VALID,
        as_of,
        numerator.period_kind,
        units,
        numerator.currency,
        inputs,
    )


def _ttm(
    facts: tuple[Fact, ...], name: str, as_of: date
) -> tuple[float, str, tuple[str, ...]] | MetricStatus:
    rows = sorted(_eligible(facts, name, as_of), key=lambda f: f.period_end)
    rows = [f for f in rows if f.period_end <= as_of and f.period_kind == "quarter"]
    if len(rows) < 4:
        return MetricStatus.INSUFFICIENT_HISTORY
    rows = rows[-4:]
    values = tuple(f.value for f in rows)
    if any(value is None for value in values):
        return MetricStatus.MISSING
    if any(
        (b.period_end - a.period_end).days not in range(80, 105) for a, b in zip(rows, rows[1:])
    ):
        return MetricStatus.INSUFFICIENT_HISTORY
    return sum(value for value in values if value is not None), "TTM", tuple(f.name for f in rows)


def _calculate_metric(
    name: str,
    raw_facts: Mapping[str, Fact] | Iterable[Fact],
    as_of: date,
    market: MarketSnapshot | None = None,
) -> MetricResult:
    """Calculate one baseline metric from normalized facts."""
    facts = _facts(raw_facts)
    n = name.lower().replace("/", "_").replace(" ", "_")
    if n in {
        "revenue",
        "operating_income",
        "ebitda",
        "net_income",
        "net_income_attributable_common",
        "operating_cash_flow",
    }:
        row = _latest(facts, n, as_of)
        return (
            _missing(n, as_of, "currency")
            if row is None
            else _result(
                n,
                row.value,
                MetricStatus.VALID if row.value is not None else MetricStatus.MISSING,
                as_of,
                row.period_kind,
                row.units,
                row.currency,
                (row.name,),
            )
        )
    if n == "gross_profit":
        revenue, cost = _latest(facts, "revenue", as_of), _latest(facts, "cost_of_revenue", as_of)
        if revenue is None or cost is None:
            return _missing(n, as_of, "currency", "revenue", "cost_of_revenue")
        if revenue.period_end != cost.period_end:
            return _result(
                n,
                None,
                MetricStatus.PERIOD_MISMATCH,
                as_of,
                revenue.period_kind,
                revenue.units,
                revenue.currency,
                ("revenue", "cost_of_revenue"),
            )
        return _result(
            n,
            revenue.value - cost.value
            if revenue.value is not None and cost.value is not None
            else None,
            MetricStatus.VALID
            if revenue.value is not None and cost.value is not None
            else MetricStatus.MISSING,
            as_of,
            revenue.period_kind,
            revenue.units,
            revenue.currency,
            ("revenue", "cost_of_revenue"),
        )
    if n in {"book_value", "common_equity"}:
        row = _latest(facts, "common_equity", as_of)
        return (
            _missing("book_value", as_of, "currency", "common_equity")
            if row is None
            else _result(
                "book_value",
                row.value,
                MetricStatus.VALID if row.value is not None else MetricStatus.MISSING,
                as_of,
                row.period_kind,
                row.units,
                row.currency,
                (row.name,),
                version="book_value_common_equity_v1",
            )
        )
    if n in {"enterprise_value", "ev"}:
        market_cap_result = _calculate_metric("market_cap", facts, as_of, market)
        debt = _latest(facts, "total_debt", as_of)
        cash = _latest(facts, "cash_and_equivalents", as_of) or _latest(facts, "cash", as_of)
        preferred = _latest(facts, "preferred_equity", as_of)
        nci = _latest(facts, "non_controlling_interest", as_of)
        if market_cap_result.value is None or debt is None or cash is None or debt.value is None or cash.value is None:
            return _missing("enterprise_value", as_of, market.currency if market else "currency",
                            "market_cap", "total_debt", "cash_and_equivalents")
        if market is not None and market.currency != (debt.currency or market.currency):
            return _result("enterprise_value", None, MetricStatus.PERIOD_MISMATCH, as_of,
                           "point_in_time", market.currency, market.currency,
                           ("market_cap", "total_debt", "cash_and_equivalents"),
                           "currency mismatch")
        market_value = market_cap_result.value
        debt_value = debt.value
        cash_value = cash.value
        value = market_value + debt_value + (preferred.value if preferred and preferred.value is not None else 0.0) \
            + (nci.value if nci and nci.value is not None else 0.0) - cash_value
        notes: list[str] = []
        if preferred is None:
            notes.append("preferred equity unavailable; assumed zero for EV approximation")
        if nci is None:
            notes.append("non-controlling interest unavailable; assumed zero for EV approximation")
        return _result("enterprise_value", value, MetricStatus.VALID, as_of, "point_in_time",
                       market.currency if market else (debt.currency or "currency"),
                       market.currency if market else (debt.currency or "currency"),
                       ("market_cap", "total_debt", "cash_and_equivalents", "preferred_equity", "non_controlling_interest"),
                       *notes, version="enterprise_value_v1")
    if n in {"price_earnings", "pe", "pe_ttm", "trailing_pe"}:
        if market is None or market.price is None:
            return _missing("pe_ttm", as_of, "multiple", "price", "ttm_eps")
        eps = _calculate_metric("ttm_eps", facts, as_of, market)
        if eps.status is not MetricStatus.VALID or eps.value is None:
            return _result("pe_ttm", None, eps.status, as_of, "TTM", "multiple", market.currency,
                           ("price", "ttm_eps"), "trailing twelve-month EPS required",
                           version="price_to_earnings_ttm_v1")
        if eps.value <= 0:
            return _result("pe_ttm", None, MetricStatus.NOT_MEANINGFUL, as_of, "TTM", "multiple",
                           market.currency, ("price", "ttm_eps"), "EPS must be positive",
                           version="price_to_earnings_ttm_v1")
        return _result("pe_ttm", market.price / eps.value, MetricStatus.VALID, as_of, "TTM",
                       "multiple", market.currency, ("price", "ttm_eps"),
                       version="price_to_earnings_ttm_v1")
    if n in {"book_value_per_share", "bvps"}:
        equity = _latest(facts, "common_equity", as_of)
        if equity is None or market is None or market.shares_outstanding is None:
            return _missing("book_value_per_share", as_of, "currency/share", "common_equity", "shares_outstanding")
        if market.shares_outstanding <= 0:
            return _result("book_value_per_share", None, MetricStatus.NOT_MEANINGFUL, as_of,
                           equity.period_kind, "currency/share", equity.currency,
                           ("common_equity", "shares_outstanding"), "shares must be positive",
                           version="book_value_per_share_v1")
        if equity.value is None:
            return _missing("book_value_per_share", as_of, "currency/share", "common_equity", "shares_outstanding")
        return _result("book_value_per_share", equity.value / market.shares_outstanding,
                       MetricStatus.VALID, as_of, equity.period_kind, "currency/share", equity.currency,
                       ("common_equity", "shares_outstanding"), version="book_value_per_share_v1")
    if n in {"price_book", "pb", "price_to_book"}:
        equity = _latest(facts, "common_equity", as_of)
        market_cap_result = _calculate_metric("market_cap", facts, as_of, market)
        if equity is None or market_cap_result.value is None:
            return _missing("price_to_book", as_of, "multiple", "market_cap", "common_equity")
        if equity.value is None:
            return _missing("price_to_book", as_of, "multiple", "market_cap", "common_equity")
        if equity.value <= 0:
            return _result("price_to_book", None, MetricStatus.NOT_MEANINGFUL, as_of,
                           equity.period_kind, "multiple", equity.currency,
                           ("market_cap", "common_equity"), "common equity must be positive",
                           version="price_to_book_common_equity_v1")
        return _result("price_to_book", market_cap_result.value / equity.value,
                       MetricStatus.VALID, as_of, equity.period_kind, "multiple", equity.currency,
                       ("market_cap", "common_equity"), version="price_to_book_common_equity_v1")
    if n in {"graham_number", "graham"}:
        eps = _calculate_metric("ttm_eps", facts, as_of, market)
        bvps = _calculate_metric("book_value_per_share", facts, as_of, market)
        if eps.status is not MetricStatus.VALID or bvps.status is not MetricStatus.VALID:
            status = (MetricStatus.NOT_MEANINGFUL if eps.status is MetricStatus.VALID and bvps.status is MetricStatus.VALID
                      else MetricStatus.MISSING)
            return _result("graham_number", None, status, as_of, "TTM/point_in_time", "currency/share",
                           market.currency if market else None, ("ttm_eps", "book_value_per_share"),
                           "requires positive EPS and BVPS", version="graham_number_v1")
        if eps.value is None or bvps.value is None or eps.value <= 0 or bvps.value <= 0:
            return _result("graham_number", None, MetricStatus.NOT_MEANINGFUL, as_of,
                           "TTM/point_in_time", "currency/share", market.currency if market else None,
                           ("ttm_eps", "book_value_per_share"),
                           "negative or zero EPS/BVPS is economically not meaningful",
                           version="graham_number_v1")
        from math import sqrt
        return _result("graham_number", sqrt(22.5 * eps.value * bvps.value), MetricStatus.VALID,
                       as_of, "TTM/point_in_time", "currency/share", market.currency if market else None,
                       ("ttm_eps", "book_value_per_share"), "classic 22.5 variant",
                       version="graham_number_v1")
    if n in {"roic", "roic_standard", "roic_simplified"}:
        nopat = _latest(facts, "nopat", as_of)
        beginning = _latest(facts, "invested_capital_begin", as_of)
        ending = _latest(facts, "invested_capital_end", as_of)
        if n != "roic_simplified" and nopat and beginning and ending and all(
            row.value is not None for row in (nopat, beginning, ending)
        ):
            beginning_value = beginning.value
            ending_value = ending.value
            nopat_value = nopat.value
            assert beginning_value is not None and ending_value is not None and nopat_value is not None
            average = (beginning_value + ending_value) / 2
            if average <= 0:
                return _result("roic_standard", None, MetricStatus.NOT_MEANINGFUL, as_of,
                               nopat.period_kind, "%", nopat.currency,
                               ("nopat", "invested_capital_begin", "invested_capital_end"),
                               "average invested capital must be positive",
                               version="roic_nopat_avg_invested_capital_v1")
            return _result("roic_standard", nopat_value / average * 100, MetricStatus.VALID,
                           as_of, nopat.period_kind, "%", nopat.currency,
                           ("nopat", "invested_capital_begin", "invested_capital_end"),
                           "NOPAT divided by average beginning/end invested capital",
                           version="roic_nopat_avg_invested_capital_v1")
        capital = _latest(facts, "invested_capital", as_of)
        if nopat is None or capital is None or nopat.value is None or capital.value is None:
            return _missing("roic_simplified" if n == "roic_simplified" else "roic", as_of, "%",
                            "nopat", "invested_capital")
        if capital.value <= 0:
            return _result("roic_simplified" if n == "roic_simplified" else "roic", None,
                           MetricStatus.NOT_MEANINGFUL, as_of, nopat.period_kind, "%", nopat.currency,
                           ("nopat", "invested_capital"), "invested capital must be positive",
                           version="roic_simplified_v1")
        return _result("roic_simplified" if n == "roic_simplified" else "roic", nopat.value / capital.value * 100,
                       MetricStatus.VALID, as_of, nopat.period_kind, "%", nopat.currency,
                       ("nopat", "invested_capital"), "simplified point-in-time invested capital variant",
                       version="roic_simplified_v1")
    if n in {
        "operating_margin",
        "net_margin",
        "revenue_per_share",
        "diluted_eps",
        "basic_eps",
        "current_ratio",
        "debt_equity",
        "price_sales",
        "price_book",
        "ev_revenue",
        "ev_ebitda",
    }:
        pairs = {
            "operating_margin": ("operating_income", "revenue", "%"),
            "net_margin": ("net_income_attributable_common", "revenue", "%"),
            "revenue_per_share": ("revenue", "weighted_avg_diluted_shares", "currency/share"),
            "diluted_eps": (
                "net_income_attributable_common",
                "weighted_avg_diluted_shares",
                "currency/share",
            ),
            "basic_eps": (
                "net_income_attributable_common",
                "weighted_avg_basic_shares",
                "currency/share",
            ),
            "current_ratio": ("current_assets", "current_liabilities", "x"),
            "debt_equity": ("total_debt", "common_equity", "x"),
        }
        if n in pairs:
            a, b, unit = pairs[n]
            x, y = _latest(facts, a, as_of), _latest(facts, b, as_of)
            if x is None or y is None:
                return _missing(n, as_of, unit, a, b)
            result = _divide(n, x, y, as_of, unit, negative_denominator=n == "debt_equity")
            if result.status is MetricStatus.VALID and n.endswith("margin"):
                assert result.value is not None
                return _result(
                    n,
                    result.value * 100,
                    result.status,
                    as_of,
                    result.period,
                    unit,
                    result.currency,
                    result.inputs,
                )
            return result
    if n == "ttm_revenue":
        ttm_result = _ttm(facts, "revenue", as_of)
        revenue_row = _latest(facts, "revenue", as_of)
        return (
            _result(
                n,
                ttm_result[0],
                MetricStatus.VALID,
                as_of,
                ttm_result[1],
                "currency",
                revenue_row.currency if revenue_row is not None else None,
                ttm_result[2],
            )
            if isinstance(ttm_result, tuple)
            else _result(
                n,
                None,
                ttm_result,
                as_of,
                "TTM",
                "currency",
                None,
                ("revenue",),
            )
        )
    if n in {"ttm_eps", "ttm_ebitda", "ttm_operating_cash_flow", "levered_fcf"}:
        source = {
            "ttm_eps": "diluted_eps",
            "ttm_ebitda": "ebitda",
            "ttm_operating_cash_flow": "operating_cash_flow",
        }.get(n)
        if source:
            ttm_result = _ttm(facts, source, as_of)
            source_row = _latest(facts, source, as_of)
            currency = source_row.currency if source_row is not None else None
            return (
                _result(
                    n,
                    ttm_result[0],
                    MetricStatus.VALID,
                    as_of,
                    ttm_result[1],
                    "currency/share" if n == "ttm_eps" else "currency",
                    currency,
                    ttm_result[2],
                )
                if isinstance(ttm_result, tuple)
                else _result(
                    n,
                    None,
                    ttm_result,
                    as_of,
                    "TTM",
                    "currency/share" if n == "ttm_eps" else "currency",
                    currency,
                    (source,),
                )
            )
        ocf, capex = (
            _latest(facts, "operating_cash_flow", as_of),
            _latest(facts, "capital_expenditures", as_of),
        )
        if ocf is None or capex is None:
            return _missing(n, as_of, "currency", "operating_cash_flow", "capital_expenditures")
        if ocf.period_end != capex.period_end:
            return _result(
                n,
                None,
                MetricStatus.PERIOD_MISMATCH,
                as_of,
                ocf.period_kind,
                ocf.units,
                ocf.currency,
                (ocf.name, capex.name),
            )
        return _result(
            n,
            ocf.value - abs(capex.value)
            if ocf.value is not None and capex.value is not None
            else None,
            MetricStatus.VALID
            if ocf.value is not None and capex.value is not None
            else MetricStatus.MISSING,
            as_of,
            ocf.period_kind,
            ocf.units,
            ocf.currency,
            (ocf.name, capex.name),
            "capex is normalized as a positive outflow",
        )
    if n == "market_cap":
        if market is None or market.price is None or market.shares_outstanding is None:
            return _missing(n, as_of, "currency", "price", "shares_outstanding")
        if market.price == 0 or market.shares_outstanding == 0:
            return _result(
                n,
                None,
                MetricStatus.ZERO_DENOMINATOR,
                as_of,
                "point_in_time",
                market.currency,
                market.currency,
                ("price", "shares_outstanding"),
            )
        return _result(
            n,
            market.price * market.shares_outstanding,
            MetricStatus.VALID,
            as_of,
            "point_in_time",
            market.currency,
            market.currency,
            ("price", "shares_outstanding"),
        )
    if n in {"roa", "roe"}:
        numerator_name, denominator_name = (
            ("net_income", "total_assets")
            if n == "roa"
            else ("net_income_attributable_common", "common_equity")
        )
        income = _ttm(facts, numerator_name, as_of)
        ends = sorted(_eligible(facts, denominator_name, as_of), key=lambda f: f.period_end)
        if not isinstance(income, tuple) or len(ends) < 2:
            return _result(
                n,
                None,
                MetricStatus.INSUFFICIENT_HISTORY,
                as_of,
                "TTM",
                "%",
                None,
                (numerator_name, denominator_name),
            )
        avg = (
            (ends[-2].value + ends[-1].value) / 2
            if ends[-2].value is not None and ends[-1].value is not None
            else None
        )
        if avg is None:
            return _missing(n, as_of, "%", numerator_name, denominator_name)
        if avg <= 0:
            return _result(
                n,
                None,
                MetricStatus.NEGATIVE_NOT_MEANINGFUL if avg < 0 else MetricStatus.ZERO_DENOMINATOR,
                as_of,
                "TTM",
                "%",
                ends[-1].currency,
                (numerator_name, denominator_name),
            )
        return _result(
            n,
            income[0] / avg * 100,
            MetricStatus.VALID,
            as_of,
            "TTM",
            "%",
            ends[-1].currency,
            (numerator_name, denominator_name),
        )
    return _result(
        n,
        None,
        MetricStatus.NOT_APPLICABLE,
        as_of,
        "unknown",
        "unknown",
        None,
        (),
        "metric is outside the B1 baseline",
    )


def fact_from_observation(observation: MetricObservation) -> Fact:
    """Adapt one canonical observation without copying its provenance metadata."""
    period = observation.provenance.period
    if period is None:
        raise ValueError("fundamental observations require a reporting period")
    available_at = observation.provenance.available_at
    return Fact(
        name=observation.name,
        value=observation.value,
        period_start=period.start,
        period_end=observation.provenance.period_end or period.end,
        period_kind=period.kind,
        units=observation.provenance.units or "unknown",
        currency=observation.provenance.currency,
        available_at=available_at.date() if available_at else observation.provenance.effective_date,
        source=observation.provenance.source,
        provenance=observation.provenance,
    )


def calculate_metric(
    name: str,
    raw_facts: Mapping[str, Fact] | Iterable[Fact],
    as_of: date,
    market: MarketSnapshot | None = None,
) -> MetricResult:
    """Calculate a metric and retain provenance references from its input facts."""
    facts = _facts(raw_facts)
    result = _calculate_metric(name, facts, as_of, market)
    names = set(result.inputs)
    provenance = tuple(f.provenance for f in facts if f.name in names and f.provenance is not None)
    if market and names.intersection({"price", "market_cap", "shares_outstanding"}) and market.provenance is not None:
        provenance += (market.provenance,)
    return replace(result, source_provenance=provenance)


BASELINE_METRICS = (
    "market_cap",
    "ttm_revenue",
    "ttm_eps",
    "gross_profit",
    "operating_margin",
    "net_margin",
    "roa",
    "roe",
    "current_ratio",
    "debt_equity",
    "ttm_operating_cash_flow",
    "levered_fcf",
)


def calculate_baseline(
    facts: Mapping[str, Fact] | Iterable[Fact], as_of: date, market: MarketSnapshot | None = None
) -> tuple[MetricResult, ...]:
    """Return the coherent B1 valuation, health, profitability, cash-flow set."""
    return tuple(calculate_metric(name, facts, as_of, market) for name in BASELINE_METRICS)
