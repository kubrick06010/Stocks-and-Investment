"""Versioned Graham criteria over supplied metric observations.

The functions are deliberately provider- and storage-free. Thresholds are
explicit inputs so historical literal and modernized variants cannot be
confused.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite
from typing import Mapping

from stocks_investment.domain.research_engine import (
    AnalysisStatus, CriterionResult, CriterionStatus, FactorObservation,
)
from stocks_investment.fundamentals.engine import Fact, MarketSnapshot, MetricResult, MetricStatus

DEFENSIVE_VERSION = "graham_defensive_literal_v1"
ENTERPRISING_VERSION = "graham_enterprising_literal_v1"
MODERNIZED_DEFENSIVE_VERSION = "graham_defensive_modernized_v1"
MODERNIZED_ENTERPRISING_VERSION = "graham_enterprising_modernized_v1"
GRAHAM_NUMBER_VERSION = "graham_number_interpretation_v1"
NCAV_VERSION = "ncav_net_net_v1"
MARGIN_OF_SAFETY_VERSION = "margin_of_safety_v1"


@dataclass(frozen=True, slots=True)
class GrahamThresholds:
    minimum_revenue: float = 0.0
    minimum_current_ratio: float = 2.0
    maximum_pe: float = 15.0
    maximum_pb: float = 1.5
    minimum_positive_earnings_years: int = 10
    minimum_earnings_growth: float = 1 / 3
    version: str = "graham_defensive_historical_v1"


def _observation(name: str, value: float | None, as_of: date, status: AnalysisStatus = AnalysisStatus.VALID) -> FactorObservation:
    return FactorObservation(name, value, status, "value", as_of, "as supplied", "factor-input-v1")


def _criterion(name: str, observed: float | None, threshold: float | int | None, as_of: date, *, passed: bool | None, rationale: str, version: str) -> CriterionResult:
    if passed is None:
        status = CriterionStatus.INSUFFICIENT_DATA
    else:
        status = CriterionStatus.PASS if passed else CriterionStatus.FAIL
    status_obs = AnalysisStatus.VALID if observed is not None and isfinite(observed) else AnalysisStatus.MISSING
    return CriterionResult(name, version, observed, threshold, status, passed, rationale, (_observation(name, observed, as_of, status_obs),))


def evaluate_graham_defensive(metrics: Mapping[str, float | None], *, as_of: date, thresholds: GrahamThresholds = GrahamThresholds()) -> tuple[CriterionResult, ...]:
    """Evaluate the historical defensive checklist without collapsing missing data."""
    def check(name: str, threshold: float | int, relation: str) -> CriterionResult:
        value = metrics.get(name)
        if value is None:
            return _criterion(name, None, threshold, as_of, passed=None, rationale="required observation missing", version=thresholds.version)
        passed = value >= threshold if relation == ">=" else value <= threshold
        return _criterion(name, value, threshold, as_of, passed=passed, rationale=f"observed {value:g} {relation} threshold {threshold:g}", version=thresholds.version)
    return (
        check("revenue", thresholds.minimum_revenue, ">="),
        check("current_ratio", thresholds.minimum_current_ratio, ">="),
        check("positive_earnings_years", thresholds.minimum_positive_earnings_years, ">="),
        check("eps_growth", thresholds.minimum_earnings_growth, ">="),
        check("pe_ttm", thresholds.maximum_pe, "<="),
        check("price_to_book", thresholds.maximum_pb, "<="),
    )


def evaluate_graham_enterprising(metrics: Mapping[str, float | None], *, as_of: date,
                                 version: str = "graham_enterprising_v1") -> tuple[CriterionResult, ...]:
    """Evaluate a separately identified, configurable enterprising baseline."""
    thresholds = GrahamThresholds(minimum_current_ratio=1.5, maximum_pe=15.0,
                                  maximum_pb=1.5, minimum_positive_earnings_years=5,
                                  minimum_earnings_growth=0.0, version=version)
    return evaluate_graham_defensive(metrics, as_of=as_of, thresholds=thresholds)


def _metric_observation(metric: MetricResult) -> FactorObservation:
    status = AnalysisStatus.VALID if metric.status is MetricStatus.VALID else AnalysisStatus.MISSING
    if metric.status is MetricStatus.NOT_MEANINGFUL:
        status = AnalysisStatus.NOT_MEANINGFUL
    return FactorObservation(metric.name, metric.value if status is AnalysisStatus.VALID else None,
                             status, metric.units, metric.as_of, metric.period, metric.version,
                             source_metric=metric.name, source_provenance=metric.source_provenance)


def evaluate_metric_threshold(metric: MetricResult, threshold: float, *, operator: str = "<=",
                              criterion_name: str | None = None, version: str = "threshold_v1") -> CriterionResult:
    """Evaluate one validated metric; missing and non-meaningful are not decisions."""
    if metric.status is not MetricStatus.VALID or metric.value is None:
        return CriterionResult(criterion_name or metric.name, version, None, threshold,
                               CriterionStatus.INSUFFICIENT_DATA, None,
                               f"{metric.name} is {metric.status.value}; no decision",
                               (_metric_observation(metric),))
    checks = {"<=": metric.value <= threshold, ">=": metric.value >= threshold,
              "<": metric.value < threshold, ">": metric.value > threshold}
    if operator not in checks:
        raise ValueError(f"unsupported operator: {operator}")
    passed = checks[operator]
    return CriterionResult(criterion_name or metric.name, version, metric.value, threshold,
                           CriterionStatus.PASS if passed else CriterionStatus.FAIL, passed,
                           f"{metric.name}={metric.value:g} {operator} {threshold:g}",
                           (_metric_observation(metric),))


def _latest(facts: tuple[Fact, ...], name: str, as_of: date) -> Fact | None:
    rows = [f for f in facts if f.name == name and f.period_end <= as_of and
            (f.available_at is None or f.available_at <= as_of)]
    return max(rows, key=lambda item: item.period_end, default=None)


def calculate_ncav(facts: Mapping[str, Fact] | tuple[Fact, ...] | list[Fact], *, as_of: date) -> MetricResult:
    """Classic NCAV: current assets minus total liabilities."""
    rows = tuple(facts.values()) if isinstance(facts, Mapping) else tuple(facts)
    assets, liabilities = _latest(rows, "current_assets", as_of), _latest(rows, "total_liabilities", as_of)
    if assets is None or liabilities is None or assets.value is None or liabilities.value is None:
        return MetricResult("ncav", None, MetricStatus.MISSING, as_of, "point_in_time", "currency", None,
                            ("current_assets", "total_liabilities"), version=NCAV_VERSION)
    provenance = tuple(item for item in (assets.provenance, liabilities.provenance) if item is not None)
    return MetricResult("ncav", assets.value - liabilities.value, MetricStatus.VALID, as_of,
                        "point_in_time", assets.units, assets.currency,
                        (assets.name, liabilities.name), version=NCAV_VERSION,
                        notes=("classic NCAV; no liquidation discount or quality adjustment",),
                        source_provenance=provenance)


def calculate_ncav_per_share(ncav: MetricResult, market: MarketSnapshot) -> MetricResult:
    if ncav.status is not MetricStatus.VALID or ncav.value is None:
        return MetricResult("ncav_per_share", None, ncav.status, ncav.as_of, ncav.period,
                            "currency/share", ncav.currency, ncav.inputs + ("shares_outstanding",),
                            version=NCAV_VERSION, notes=ncav.notes, source_provenance=ncav.source_provenance)
    if market.shares_outstanding is None:
        status = MetricStatus.MISSING
        value = None
    elif market.shares_outstanding <= 0:
        status = MetricStatus.NOT_MEANINGFUL
        value = None
    else:
        status = MetricStatus.VALID
        value = ncav.value / market.shares_outstanding
    return MetricResult("ncav_per_share", value, status, ncav.as_of, ncav.period, "currency/share",
                        ncav.currency, ("ncav", "shares_outstanding"), version=NCAV_VERSION,
                        notes=("shares must be positive",) if status is MetricStatus.NOT_MEANINGFUL else (),
                        source_provenance=ncav.source_provenance)


def _price_observation(price: MetricResult | float, as_of: date) -> tuple[FactorObservation, ...]:
    return (_metric_observation(price),) if isinstance(price, MetricResult) else ()


def interpret_graham_number(graham_number: MetricResult, price: MetricResult | float) -> CriterionResult:
    observed = price.value if isinstance(price, MetricResult) else price
    observations = (_metric_observation(graham_number),) + _price_observation(price, graham_number.as_of)
    if graham_number.status is not MetricStatus.VALID or graham_number.value is None or observed is None:
        return CriterionResult("price_below_graham_number", GRAHAM_NUMBER_VERSION, None, None,
                               CriterionStatus.INSUFFICIENT_DATA, None, "Graham Number or price unavailable", observations)
    if graham_number.value <= 0 or observed < 0:
        return CriterionResult("price_below_graham_number", GRAHAM_NUMBER_VERSION, observed, graham_number.value,
                               CriterionStatus.NOT_APPLICABLE, None, "positive Graham Number and non-negative price required", observations)
    passed = observed <= graham_number.value
    return CriterionResult("price_below_graham_number", GRAHAM_NUMBER_VERSION, observed, graham_number.value,
                           CriterionStatus.PASS if passed else CriterionStatus.FAIL, passed,
                           "price is at or below the Graham Number" if passed else "price exceeds the Graham Number", observations)


def evaluate_net_net(ncav_per_share: MetricResult, price: MetricResult | float) -> CriterionResult:
    observed = price.value if isinstance(price, MetricResult) else price
    observations = (_metric_observation(ncav_per_share),) + _price_observation(price, ncav_per_share.as_of)
    if ncav_per_share.status is not MetricStatus.VALID or ncav_per_share.value is None or observed is None:
        return CriterionResult("net_net_price", NCAV_VERSION, None, 2 / 3,
                               CriterionStatus.INSUFFICIENT_DATA, None, "NCAV/share or price unavailable", observations)
    if ncav_per_share.value <= 0 or observed < 0:
        return CriterionResult("net_net_price", NCAV_VERSION, observed, 2 / 3,
                               CriterionStatus.NOT_APPLICABLE, None, "positive NCAV/share and non-negative price required", observations)
    ratio = observed / ncav_per_share.value
    passed = ratio <= 2 / 3
    return CriterionResult("net_net_price", NCAV_VERSION, ratio, 2 / 3,
                           CriterionStatus.PASS if passed else CriterionStatus.FAIL, passed,
                           f"price/NCAV per share={ratio:g}; limit=2/3", observations)


def evaluate_margin_of_safety(intrinsic_value: MetricResult, price: MetricResult | float,
                             *, minimum: float = 1 / 3) -> CriterionResult:
    observed = price.value if isinstance(price, MetricResult) else price
    observations = (_metric_observation(intrinsic_value),) + _price_observation(price, intrinsic_value.as_of)
    if intrinsic_value.status is not MetricStatus.VALID or intrinsic_value.value is None or observed is None:
        return CriterionResult("margin_of_safety", MARGIN_OF_SAFETY_VERSION, None, minimum,
                               CriterionStatus.INSUFFICIENT_DATA, None, "intrinsic value or price unavailable", observations)
    if intrinsic_value.value <= 0 or observed < 0 or not isfinite(minimum) or not 0 <= minimum < 1:
        return CriterionResult("margin_of_safety", MARGIN_OF_SAFETY_VERSION, None, minimum,
                               CriterionStatus.NOT_APPLICABLE, None, "positive intrinsic value and 0<=minimum<1 required", observations)
    margin = 1 - observed / intrinsic_value.value
    passed = margin >= minimum
    return CriterionResult("margin_of_safety", MARGIN_OF_SAFETY_VERSION, margin, minimum,
                           CriterionStatus.PASS if passed else CriterionStatus.FAIL, passed,
                           f"margin={margin:g}; required>={minimum:g}", observations)


class DefensiveGrahamStrategy:
    name = "graham_defensive_literal"
    version = DEFENSIVE_VERSION

    def evaluate(self, metrics: Mapping[str, float | None], *, as_of: date) -> tuple[CriterionResult, ...]:
        return evaluate_graham_defensive(metrics, as_of=as_of,
                                         thresholds=GrahamThresholds(version=self.version))


class EnterprisingGrahamStrategy:
    name = "graham_enterprising_literal"
    version = ENTERPRISING_VERSION

    def evaluate(self, metrics: Mapping[str, float | None], *, as_of: date) -> tuple[CriterionResult, ...]:
        return evaluate_graham_enterprising(metrics, as_of=as_of, version=self.version)


class ModernizedDefensiveGrahamStrategy:
    name = "graham_defensive_modernized"
    version = MODERNIZED_DEFENSIVE_VERSION

    def evaluate(self, metrics: Mapping[str, float | None], *, as_of: date) -> tuple[CriterionResult, ...]:
        return evaluate_graham_defensive(metrics, as_of=as_of,
                                         thresholds=GrahamThresholds(minimum_current_ratio=1.5,
                                                                      maximum_pe=20.0, maximum_pb=3.0,
                                                                      version=self.version))


class ModernizedEnterprisingGrahamStrategy:
    name = "graham_enterprising_modernized"
    version = MODERNIZED_ENTERPRISING_VERSION

    def evaluate(self, metrics: Mapping[str, float | None], *, as_of: date) -> tuple[CriterionResult, ...]:
        return evaluate_graham_defensive(metrics, as_of=as_of,
                                         thresholds=GrahamThresholds(minimum_current_ratio=1.2,
                                                                      maximum_pe=20.0, maximum_pb=3.0,
                                                                      version=self.version))
