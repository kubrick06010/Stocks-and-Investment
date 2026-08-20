"""Real-data pilot for the licensed India PIT/survivorship sample.

The source bundle is CC BY 4.0 and contains three independently useful tables:
historical listing life spans, total-return prices, and as-reported fundamentals
stamped with announcement dates.  This module turns that evidence into a small,
explicit factor-outcome cohort without provider calls or current-data fallback.
"""

from __future__ import annotations

import csv
import hashlib
import io
import math
import zipfile
from bisect import bisect_left
from dataclasses import dataclass
from datetime import date
from statistics import mean
from typing import Mapping

from stocks_investment.domain import FactorOutcomeObservation, Ticker
from stocks_investment.statistical_validation.artifacts import DatasetArtifactSpec


FACTOR_NAME = "profitability_margin"
FACTOR_VERSION = "profitability_margin_pat_over_revenue_percentile_v1"
UNIVERSE_VERSION = "FINANCEBROSKI_NSE_BSE_TRADING_INTERVAL_SAMPLE_KAGGLE_V3"
BENCHMARK_VERSION = "FINANCEBROSKI_99_EQW_TR_PROXY_V1"

_REQUIRED_FILES = (
    "fundamentals_sample.csv",
    "prices_sample.csv",
    "survivorship_universe.csv",
)


@dataclass(frozen=True, slots=True)
class IndiaPitBundleSpec:
    artifact: DatasetArtifactSpec
    inner_sha256: Mapping[str, str]

    def __post_init__(self) -> None:
        if set(self.inner_sha256) != set(_REQUIRED_FILES):
            raise ValueError("India PIT bundle must hash all three canonical files")
        for digest in self.inner_sha256.values():
            if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest.lower()):
                raise ValueError("India PIT inner hashes must be hexadecimal SHA-256 digests")


@dataclass(frozen=True, slots=True)
class IndiaPitBuildResult:
    observations: tuple[FactorOutcomeObservation, ...]
    universe_securities: int
    inactive_securities: int
    price_securities: int
    fundamental_securities: int
    research_dates: tuple[date, ...]
    terminal_cash_approximations: int
    unavailable_outcomes: int
    source_sha256: str


@dataclass(frozen=True, slots=True)
class _UniverseRow:
    first_traded: date
    last_traded: date
    inactive: bool


@dataclass(frozen=True, slots=True)
class _FundamentalRow:
    period_end: date
    announce_date: date
    pat_margin: float


@dataclass(frozen=True, slots=True)
class _ReturnMeasurement:
    value: float | None
    terminal_cash_approximation: bool = False


def build_india_pit_observations(
    spec: IndiaPitBundleSpec,
    *,
    research_dates: tuple[date, ...],
    horizons: tuple[str, ...] = ("3M", "12M"),
) -> IndiaPitBuildResult:
    """Build PIT factor/outcome observations from one immutable source bundle."""

    if not research_dates or tuple(sorted(set(research_dates))) != research_dates:
        raise ValueError("research dates must be non-empty, unique, and sorted")
    months = tuple(_horizon_months(horizon) for horizon in horizons)
    if len(set(horizons)) != len(horizons):
        raise ValueError("outcome horizons must be unique")

    content = spec.artifact.path.read_bytes()
    source_digest = hashlib.sha256(content).hexdigest()
    if source_digest != spec.artifact.sha256.lower():
        raise ValueError("India PIT bundle SHA-256 mismatch")
    with zipfile.ZipFile(io.BytesIO(content)) as bundle:
        if tuple(sorted(bundle.namelist())) != tuple(sorted(_REQUIRED_FILES)):
            raise ValueError("India PIT bundle file set does not match the declared schema")
        tables: dict[str, bytes] = {}
        for name in _REQUIRED_FILES:
            payload = bundle.read(name)
            if hashlib.sha256(payload).hexdigest() != spec.inner_sha256[name].lower():
                raise ValueError(f"India PIT inner SHA-256 mismatch: {name}")
            tables[name] = payload

    universe = _load_universe(tables["survivorship_universe.csv"])
    prices = _load_prices(tables["prices_sample.csv"])
    fundamentals = _load_fundamentals(tables["fundamentals_sample.csv"])
    unknown_price_symbols = set(prices).difference(universe)
    unknown_fundamental_symbols = set(fundamentals).difference(universe)
    if unknown_price_symbols or unknown_fundamental_symbols:
        raise ValueError("India PIT observations reference symbols outside the universe inventory")
    observations: list[FactorOutcomeObservation] = []
    terminal_count = 0
    unavailable_count = 0

    for as_of in research_dates:
        latest = _latest_available_fundamentals(fundamentals, universe, as_of)
        scores = _percentile_scores({symbol: row.pat_margin for symbol, row in latest.items()})
        for horizon, horizon_months in zip(horizons, months, strict=True):
            target = _add_months(as_of, horizon_months)
            benchmark_returns = tuple(
                measurement.value
                for symbol, series in prices.items()
                if (measurement := _measure_return(series, universe.get(symbol), as_of, target)).value
                is not None
            )
            benchmark_return = mean(benchmark_returns) if benchmark_returns else None
            for symbol in sorted(latest):
                measurement = _measure_return(prices.get(symbol, ()), universe.get(symbol), as_of, target)
                if measurement.terminal_cash_approximation:
                    terminal_count += 1
                if measurement.value is None or benchmark_return is None:
                    unavailable_count += 1
                status = (
                    "measured_terminal_cash_approximation"
                    if measurement.terminal_cash_approximation and measurement.value is not None
                    else "measured" if measurement.value is not None and benchmark_return is not None
                    else "unavailable"
                )
                excess = (
                    measurement.value - benchmark_return
                    if measurement.value is not None and benchmark_return is not None
                    else None
                )
                observations.append(
                    FactorOutcomeObservation(
                        FACTOR_NAME,
                        FACTOR_VERSION,
                        f"india-pit:{as_of.isoformat()}",
                        Ticker(symbol),
                        as_of,
                        scores[symbol],
                        horizon,
                        measurement.value,
                        benchmark_return,
                        excess,
                        status,
                        UNIVERSE_VERSION,
                        BENCHMARK_VERSION,
                        "INR",
                        "quarterly",
                    )
                )

    observations.sort(
        key=lambda item: (
            item.as_of,
            item.ticker.symbol,
            item.factor_version,
            item.horizon,
        )
    )
    return IndiaPitBuildResult(
        tuple(observations),
        len(universe),
        sum(row.inactive for row in universe.values()),
        len(prices),
        len(fundamentals),
        research_dates,
        terminal_count,
        unavailable_count,
        source_digest,
    )


def _load_universe(payload: bytes) -> dict[str, _UniverseRow]:
    rows = _csv_rows(payload, (
        "symbol", "first_traded", "last_traded", "n_days", "isin",
        "continuity_id", "company_name", "listing_date", "status",
    ))
    result: dict[str, _UniverseRow] = {}
    for row in rows:
        symbol = row["symbol"].strip().upper()
        if not symbol:
            raise ValueError("India universe symbols must not be blank")
        if symbol in result:
            raise ValueError(f"duplicate India universe symbol: {symbol}")
        first_traded = date.fromisoformat(row["first_traded"])
        last_traded = date.fromisoformat(row["last_traded"])
        if last_traded < first_traded:
            raise ValueError(f"India universe dates are inverted for {symbol}")
        status = row["status"].strip().lower()
        if status not in {"active", "inactive"}:
            raise ValueError(f"unsupported India universe status for {symbol}: {status}")
        result[symbol] = _UniverseRow(
            first_traded,
            last_traded,
            status == "inactive",
        )
    return result


def _load_fundamentals(payload: bytes) -> dict[str, tuple[_FundamentalRow, ...]]:
    rows = _csv_rows(payload, (
        "symbol", "period_end", "announce_date", "consolidated", "revenue_cr",
        "pat_cr", "eps_basic", "total_income_cr", "announce_lag_days",
    ))
    grouped: dict[str, list[_FundamentalRow]] = {}
    identities: set[tuple[str, date, date]] = set()
    for row in rows:
        symbol = row["symbol"].strip().upper()
        if not symbol:
            raise ValueError("India fundamental symbols must not be blank")
        period_end = date.fromisoformat(row["period_end"])
        announce_date = date.fromisoformat(row["announce_date"])
        if announce_date < period_end:
            raise ValueError(f"India fundamental announcement precedes period end: {symbol}")
        identity = (symbol, period_end, announce_date)
        if identity in identities:
            raise ValueError(f"duplicate India fundamental identity: {identity}")
        identities.add(identity)
        revenue = _finite_float(row["revenue_cr"], "revenue_cr")
        pat = _finite_float(row["pat_cr"], "pat_cr")
        if revenue is None or pat is None or revenue <= 0:
            continue
        grouped.setdefault(symbol, []).append(_FundamentalRow(period_end, announce_date, pat / revenue))
    return {
        symbol: tuple(sorted(values, key=lambda item: (item.announce_date, item.period_end)))
        for symbol, values in grouped.items()
    }


def _load_prices(payload: bytes) -> dict[str, tuple[tuple[date, float], ...]]:
    rows = _csv_rows(payload, ("date", "symbol", "isin", "adj_close", "tr_close", "deliv_pct"))
    grouped: dict[str, list[tuple[date, float]]] = {}
    identities: set[tuple[str, date]] = set()
    for row in rows:
        symbol = row["symbol"].strip().upper()
        if not symbol:
            raise ValueError("India price symbols must not be blank")
        observed = date.fromisoformat(row["date"])
        identity = (symbol, observed)
        if identity in identities:
            raise ValueError(f"duplicate India price identity: {identity}")
        identities.add(identity)
        close = _finite_float(row["tr_close"], "tr_close")
        if close is None or close <= 0:
            continue
        grouped.setdefault(symbol, []).append((observed, close))
    return {
        symbol: tuple(sorted(values))
        for symbol, values in grouped.items()
    }


def _latest_available_fundamentals(
    fundamentals: Mapping[str, tuple[_FundamentalRow, ...]],
    universe: Mapping[str, _UniverseRow],
    as_of: date,
) -> dict[str, _FundamentalRow]:
    result: dict[str, _FundamentalRow] = {}
    for symbol, rows in fundamentals.items():
        membership = universe.get(symbol)
        if membership is None or not membership.first_traded <= as_of <= membership.last_traded:
            continue
        available = tuple(
            row for row in rows
            if row.announce_date <= as_of and row.period_end <= as_of
        )
        if available:
            result[symbol] = available[-1]
    return result


def _measure_return(
    series: tuple[tuple[date, float], ...],
    membership: _UniverseRow | None,
    start: date,
    target: date,
) -> _ReturnMeasurement:
    if not series or membership is None or not membership.first_traded <= start <= membership.last_traded:
        return _ReturnMeasurement(None)
    dates = tuple(item[0] for item in series)
    start_index = bisect_left(dates, start)
    if start_index >= len(series) or (series[start_index][0] - start).days > 10:
        return _ReturnMeasurement(None)
    end_index = bisect_left(dates, target)
    terminal = False
    if end_index >= len(series) or (series[end_index][0] - target).days > 10:
        if membership.inactive and membership.last_traded < target:
            end_index = bisect_left(dates, membership.last_traded)
            if end_index >= len(series) or dates[end_index] > membership.last_traded:
                end_index -= 1
            terminal = end_index >= start_index
        else:
            return _ReturnMeasurement(None)
    if end_index < start_index:
        return _ReturnMeasurement(None)
    start_value = series[start_index][1]
    end_value = series[end_index][1]
    return _ReturnMeasurement(end_value / start_value - 1.0, terminal)


def _percentile_scores(values: Mapping[str, float]) -> dict[str, float]:
    ordered = sorted(values.items(), key=lambda item: (item[1], item[0]))
    if len(ordered) == 1:
        return {ordered[0][0]: 50.0}
    result: dict[str, float] = {}
    index = 0
    while index < len(ordered):
        end = index
        while end + 1 < len(ordered) and ordered[end + 1][1] == ordered[index][1]:
            end += 1
        average_rank = (index + end) / 2.0
        score = 100.0 * average_rank / (len(ordered) - 1)
        for position in range(index, end + 1):
            result[ordered[position][0]] = score
        index = end + 1
    return result


def _csv_rows(payload: bytes, columns: tuple[str, ...]) -> tuple[dict[str, str], ...]:
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8")))
    if reader.fieldnames is None or tuple(reader.fieldnames) != columns:
        raise ValueError("India PIT CSV columns do not match the declared schema")
    rows: list[dict[str, str]] = []
    for line_number, row in enumerate(reader, start=2):
        if None in row or any(row.get(column) is None for column in columns):
            raise ValueError(f"India PIT CSV row {line_number} has missing columns")
        rows.append({column: str(row[column]) for column in columns})
    return tuple(rows)


def _finite_float(value: str, field: str) -> float | None:
    if value.strip() == "":
        return None
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"India PIT {field} must be finite")
    return parsed


def _horizon_months(horizon: str) -> int:
    values = {"1M": 1, "3M": 3, "6M": 6, "12M": 12}
    try:
        return values[horizon]
    except KeyError as error:
        raise ValueError(f"unsupported India PIT horizon: {horizon}") from error


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, _month_days(year, month))
    return date(year, month, day)


def _month_days(year: int, month: int) -> int:
    next_month = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    return (next_month - date(year, month, 1)).days
