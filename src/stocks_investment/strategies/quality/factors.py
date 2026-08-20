"""Versioned, pure quality/forensic calculations.

Inputs are deliberately explicit and must already be normalized by the B1
fundamentals layer.  These functions do not fetch data, impute missing values,
or turn a factor into an investment decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite
from typing import Iterable

from stocks_investment.domain.research_engine import (
    AnalysisStatus, CriterionResult, CriterionStatus, FactorObservation,
)

PIOTROSKI_F_VERSION = "piotroski_f_score_v1"
ALTMAN_Z_VERSION = "altman_z_score_v1"
BENEISH_M_VERSION = "beneish_m_score_v1"


@dataclass(frozen=True, slots=True)
class QualityResult:
    """A decomposable factor result; it intentionally contains no weighted score."""

    name: str
    version: str
    value: float | None
    status: AnalysisStatus
    as_of: date
    period: str
    units: str
    observations: tuple[FactorObservation, ...]
    criteria: tuple[CriterionResult, ...] = ()
    rationale: str = ""


@dataclass(frozen=True, slots=True)
class PiotroskiInputs:
    as_of: date
    period: str = "TTM"
    net_income: float | None = None
    net_income_prior: float | None = None
    total_assets: float | None = None
    total_assets_prior: float | None = None
    operating_cash_flow: float | None = None
    total_debt: float | None = None
    total_debt_prior: float | None = None
    current_assets: float | None = None
    current_assets_prior: float | None = None
    current_liabilities: float | None = None
    current_liabilities_prior: float | None = None
    shares_outstanding: float | None = None
    shares_outstanding_prior: float | None = None
    gross_margin: float | None = None
    gross_margin_prior: float | None = None
    revenue: float | None = None
    revenue_prior: float | None = None


@dataclass(frozen=True, slots=True)
class AltmanInputs:
    as_of: date
    working_capital: float | None = None
    retained_earnings: float | None = None
    ebit: float | None = None
    total_assets: float | None = None
    total_liabilities: float | None = None
    sales: float | None = None
    market_value_equity: float | None = None
    book_value_equity: float | None = None
    period: str = "TTM/ending balance"


@dataclass(frozen=True, slots=True)
class BeneishInputs:
    as_of: date
    receivables: float | None = None
    receivables_prior: float | None = None
    revenue: float | None = None
    revenue_prior: float | None = None
    gross_profit: float | None = None
    gross_profit_prior: float | None = None
    current_assets: float | None = None
    current_assets_prior: float | None = None
    ppe: float | None = None
    ppe_prior: float | None = None
    total_assets: float | None = None
    total_assets_prior: float | None = None
    depreciation: float | None = None
    depreciation_prior: float | None = None
    sga: float | None = None
    sga_prior: float | None = None
    total_debt: float | None = None
    total_debt_prior: float | None = None
    current_liabilities: float | None = None
    current_liabilities_prior: float | None = None
    net_income: float | None = None
    operating_cash_flow: float | None = None
    period: str = "annual"


def _obs(name: str, value: float | None, status: AnalysisStatus, x: date, period: str, units: str, source: str = "quality_input") -> FactorObservation:
    return FactorObservation(name, value if status is AnalysisStatus.VALID else None, status, units, x, period, source)


def _status(values: Iterable[float | None], *, require_positive: Iterable[float | None] = ()) -> AnalysisStatus:
    vals = tuple(values)
    if any(v is None for v in vals):
        return AnalysisStatus.MISSING
    if any(not isfinite(v) for v in vals if v is not None):
        return AnalysisStatus.NOT_MEANINGFUL
    if any(v <= 0 for v in require_positive if v is not None):
        return AnalysisStatus.NOT_MEANINGFUL
    return AnalysisStatus.VALID


def _ratio(a: float | None, b: float | None) -> tuple[float | None, AnalysisStatus]:
    status = _status((a, b), require_positive=(b,))
    if status is not AnalysisStatus.VALID or a is None or b is None:
        return None, status
    return a / b, status


def _invalid_status(statuses: Iterable[AnalysisStatus]) -> AnalysisStatus:
    statuses = tuple(statuses)
    return (AnalysisStatus.NOT_MEANINGFUL
            if AnalysisStatus.NOT_MEANINGFUL in statuses else AnalysisStatus.MISSING)


def _criteria(name: str, value: float | None, passed: bool | None, x: date, rationale: str) -> CriterionResult:
    if value is None:
        return CriterionResult(name, PIOTROSKI_F_VERSION, None, None, CriterionStatus.INSUFFICIENT_DATA, None, rationale)
    status = CriterionStatus.PASS if passed else CriterionStatus.FAIL
    return CriterionResult(name, PIOTROSKI_F_VERSION, value, 1.0, status, passed, rationale)


def piotroski_f_score(x: PiotroskiInputs) -> QualityResult:
    """Piotroski's nine binary signals, returned as criteria plus total (0..9)."""
    roa, roa_status = _ratio(x.net_income, x.total_assets)
    roa_prior, prior_status = _ratio(x.net_income_prior, x.total_assets_prior)
    current_ratio, cr_status = _ratio(x.current_assets, x.current_liabilities)
    prior_ratio, pcr_status = _ratio(x.current_assets_prior, x.current_liabilities_prior)
    values = (roa, x.operating_cash_flow, x.net_income, x.total_debt, x.total_debt_prior,
              current_ratio, prior_ratio, x.shares_outstanding, x.shares_outstanding_prior,
              x.gross_margin, x.gross_margin_prior, x.revenue, x.revenue_prior)
    observations = tuple(_obs(n, v, AnalysisStatus.VALID if v is not None else AnalysisStatus.MISSING,
                               x.as_of, x.period, "ratio" if n not in {"net_income", "operating_cash_flow"} else "currency")
                         for n, v in zip(("roa", "operating_cash_flow", "net_income", "total_debt", "total_debt_prior",
                                          "current_ratio", "current_ratio_prior", "shares_outstanding", "shares_outstanding_prior",
                                          "gross_margin", "gross_margin_prior", "revenue", "revenue_prior"), values))
    no_dilution = (x.shares_outstanding <= x.shares_outstanding_prior
                   if x.shares_outstanding is not None and x.shares_outstanding_prior is not None else None)
    margin_improved = (x.gross_margin > x.gross_margin_prior
                       if x.gross_margin is not None and x.gross_margin_prior is not None else None)
    c = (
        _criteria("positive_roa", roa, roa is not None and roa > 0, x.as_of, "current ROA is positive"),
        _criteria("positive_operating_cash_flow", x.operating_cash_flow, x.operating_cash_flow is not None and x.operating_cash_flow > 0, x.as_of, "operating cash flow is positive"),
        _criteria("roa_improvement", roa_prior if roa is not None and roa_prior is not None else None, roa is not None and roa_prior is not None and roa > roa_prior, x.as_of, "ROA improved versus the prior period"),
        _criteria("cash_flow_exceeds_net_income", x.operating_cash_flow if x.operating_cash_flow is not None and x.net_income is not None else None, x.operating_cash_flow is not None and x.net_income is not None and x.operating_cash_flow > x.net_income, x.as_of, "cash flow exceeds net income"),
        _criteria("leverage_decreased", x.total_debt if x.total_debt is not None and x.total_debt_prior is not None else None, x.total_debt is not None and x.total_debt_prior is not None and x.total_debt < x.total_debt_prior, x.as_of, "total debt decreased"),
        _criteria("liquidity_improved", current_ratio if current_ratio is not None and prior_ratio is not None else None, current_ratio is not None and prior_ratio is not None and current_ratio > prior_ratio, x.as_of, "current ratio improved"),
        _criteria("no_share_dilution", x.shares_outstanding if no_dilution is not None else None, no_dilution, x.as_of, "shares did not increase"),
        _criteria("gross_margin_improved", x.gross_margin if margin_improved is not None else None, margin_improved, x.as_of, "gross margin improved"),
        _criteria("asset_turnover_improved", x.revenue if x.revenue is not None and x.revenue_prior is not None and x.total_assets is not None and x.total_assets_prior else None,
                  x.revenue is not None and x.revenue_prior is not None and x.total_assets is not None and x.total_assets_prior is not None and x.revenue / x.total_assets > x.revenue_prior / x.total_assets_prior,
                  x.as_of, "asset turnover improved"),
    )
    valid = tuple(item for item in c if item.status is not CriterionStatus.INSUFFICIENT_DATA)
    result_status = AnalysisStatus.VALID if len(valid) == 9 else AnalysisStatus.INSUFFICIENT_HISTORY
    return QualityResult("piotroski_f_score", PIOTROSKI_F_VERSION, float(sum(item.passed is True for item in c)) if result_status is AnalysisStatus.VALID else None,
                         result_status, x.as_of, x.period, "points_0_to_9", observations, c,
                         "Nine equal binary signals; no partial credit or missing-data imputation.")


def altman_z_score(x: AltmanInputs, *, variant: str = "original_manufacturing") -> QualityResult:
    """Altman Z score for an explicit original, private, or non-manufacturer variant."""
    variants = {
        "original_manufacturing": (1.2, 1.4, 3.3, 0.6, 1.0, "market_value_equity"),
        "private_company": (0.717, 0.847, 3.107, 0.420, 0.998, "book_value_equity"),
        "non_manufacturer": (6.56, 3.26, 6.72, 1.05, None, "book_value_equity"),
    }
    if variant not in variants:
        raise ValueError(f"unsupported Altman variant: {variant}")
    a, b, c, d, e, equity_field = variants[variant]
    equity = getattr(x, equity_field)
    ratios = (_ratio(x.working_capital, x.total_assets), _ratio(x.retained_earnings, x.total_assets),
              _ratio(x.ebit, x.total_assets), _ratio(equity, x.total_liabilities), _ratio(x.sales, x.total_assets))
    required_ratios = ratios[:4] if e is None else ratios
    observations = tuple(_obs(n, v, s, x.as_of, x.period, "ratio") for n, ((v, s)) in zip(
        ("wc_to_assets", "retained_earnings_to_assets", "ebit_to_assets", "equity_to_liabilities", "sales_to_assets"), ratios))
    if any(s is not AnalysisStatus.VALID for _, s in required_ratios):
        return QualityResult("altman_z_score", f"{ALTMAN_Z_VERSION}:{variant}", None, _invalid_status(s for _, s in required_ratios), x.as_of, x.period, "z", observations, rationale=f"variant={variant}")
    ratio_values = tuple(item[0] for item in ratios)
    if e is None:
        ratio_values = ratio_values[:4] + (0.0,)
    if any(item is None for item in ratio_values):
        return QualityResult("altman_z_score", f"{ALTMAN_Z_VERSION}:{variant}", None, AnalysisStatus.MISSING, x.as_of, x.period, "z", observations, rationale=f"variant={variant}")
    x1, x2, x3, x4, x5 = (item for item in ratio_values if item is not None)
    value = a * x1 + b * x2 + c * x3 + d * x4
    if e is not None:
        value += e * x5
    return QualityResult("altman_z_score", f"{ALTMAN_Z_VERSION}:{variant}", value, AnalysisStatus.VALID, x.as_of, x.period, "z", observations, rationale=f"variant={variant}; coefficients are not interchangeable")


def beneish_m_score(x: BeneishInputs) -> QualityResult:
    """Beneish eight-variable M-score; requires two aligned annual periods."""
    def r(a: float | None, b: float | None) -> tuple[float | None, AnalysisStatus]: return _ratio(a, b)
    dsri = r(x.receivables / x.revenue if x.receivables is not None and x.revenue else None, x.receivables_prior / x.revenue_prior if x.receivables_prior is not None and x.revenue_prior else None)
    gmi = r(x.gross_profit / x.revenue if x.gross_profit is not None and x.revenue else None, x.gross_profit_prior / x.revenue_prior if x.gross_profit_prior is not None and x.revenue_prior else None)
    aqi = r(1 - ((x.current_assets + x.ppe) / x.total_assets) if x.current_assets is not None and x.ppe is not None and x.total_assets else None, 1 - ((x.current_assets_prior + x.ppe_prior) / x.total_assets_prior) if x.current_assets_prior is not None and x.ppe_prior is not None and x.total_assets_prior else None)
    sgi = r(x.revenue, x.revenue_prior)
    depi = r(x.depreciation / (x.depreciation + x.ppe) if x.depreciation is not None and x.ppe is not None and x.depreciation + x.ppe else None, x.depreciation_prior / (x.depreciation_prior + x.ppe_prior) if x.depreciation_prior is not None and x.ppe_prior is not None and x.depreciation_prior + x.ppe_prior else None)
    sgai = r(x.sga / x.revenue if x.sga is not None and x.revenue else None, x.sga_prior / x.revenue_prior if x.sga_prior is not None and x.revenue_prior else None)
    lvgi = r(((x.total_debt + x.current_liabilities) / x.total_assets) if x.total_debt is not None and x.current_liabilities is not None and x.total_assets else None, ((x.total_debt_prior + x.current_liabilities_prior) / x.total_assets_prior) if x.total_debt_prior is not None and x.current_liabilities_prior is not None and x.total_assets_prior else None)
    tata = r(x.net_income - x.operating_cash_flow if x.net_income is not None and x.operating_cash_flow is not None else None, x.total_assets)
    metrics = (dsri, gmi, aqi, sgi, depi, sgai, lvgi, tata)
    names = ("dsri", "gmi", "aqi", "sgi", "depi", "sgai", "lvgi", "tata")
    observations = tuple(_obs(n, v, s, x.as_of, x.period, "ratio") for n, (v, s) in zip(names, metrics))
    if any(s is not AnalysisStatus.VALID for _, s in metrics):
        return QualityResult("beneish_m_score", BENEISH_M_VERSION, None, _invalid_status(s for _, s in metrics), x.as_of, x.period, "score", observations, rationale="all eight annual indices are required")
    vals = tuple(v for v, _ in metrics)
    if any(item is None for item in vals):
        return QualityResult("beneish_m_score", BENEISH_M_VERSION, None, _invalid_status(s for _, s in metrics), x.as_of, x.period, "score", observations, rationale="all eight annual indices are required")
    v0, v1, v2, v3, v4, v5, v6, v7 = (item for item in vals if item is not None)
    value = -4.84 + 0.92 * v0 + 0.528 * v1 + 0.404 * v2 + 0.892 * v3 + 0.115 * v4 - 0.172 * v5 + 4.679 * v7 - 0.327 * v6
    return QualityResult("beneish_m_score", BENEISH_M_VERSION, value, AnalysisStatus.VALID, x.as_of, x.period, "score", observations, rationale="higher values are more consistent with the published manipulation-risk screen; not a probability")
