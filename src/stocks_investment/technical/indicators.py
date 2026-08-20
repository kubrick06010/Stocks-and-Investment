"""Pure technical indicators over canonical :class:`PriceBar` records.

The functions deliberately return aligned tuples.  A value is ``None`` until
enough observations exist; no missing value is silently treated as zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Sequence

from stocks_investment.domain.market import PriceAdjustmentPolicy, PriceBar

Number = Decimal
Series = tuple[Number | None, ...]


@dataclass(frozen=True, slots=True)
class TechnicalSeries:
    values: Series
    ticker: str
    adjustment_policy: PriceAdjustmentPolicy


@dataclass(frozen=True, slots=True)
class MACDResult:
    line: Series
    signal: Series
    histogram: Series
    ticker: str
    adjustment_policy: PriceAdjustmentPolicy


class Trend(StrEnum):
    UP = "up"
    DOWN = "down"
    FLAT = "flat"
    INSUFFICIENT_DATA = "insufficient_data"


def _bars(bars: Sequence[PriceBar], policy: PriceAdjustmentPolicy) -> tuple[PriceBar, ...]:
    if not isinstance(policy, PriceAdjustmentPolicy):
        raise TypeError("adjustment_policy must be a PriceAdjustmentPolicy")
    result = tuple(bars)
    if not result:
        return result
    ticker, currency = result[0].ticker, result[0].currency
    previous: date | None = None
    for bar in result:
        if bar.adjustment_policy is not policy:
            raise ValueError("all PriceBars must use the requested adjustment_policy")
        if bar.ticker != ticker or bar.currency != currency:
            raise ValueError("PriceBars must have one ticker and currency")
        if previous is not None and bar.session <= previous:
            raise ValueError("PriceBars must be in strictly increasing session order")
        if bar.session.weekday() >= 5:
            raise ValueError("weekend sessions are not valid market sessions")
        previous = bar.session
        for value in (bar.open, bar.high, bar.low, bar.close):
            if not isinstance(value, Decimal) or not value.is_finite():
                raise ValueError("PriceBars cannot contain NaN or infinite prices")
    return result


def _check_period(period: int) -> None:
    if period < 1:
        raise ValueError("period must be positive")


def _sma_values(values: Sequence[Decimal], period: int) -> Series:
    return tuple(
        None if i + 1 < period else sum(values[i + 1 - period : i + 1], Decimal(0)) / period
        for i in range(len(values))
    )


def _close(
    bars: Sequence[PriceBar], policy: PriceAdjustmentPolicy
) -> tuple[tuple[PriceBar, ...], tuple[Decimal, ...]]:
    checked = _bars(bars, policy)
    return checked, tuple(bar.close for bar in checked)


def sma(
    bars: Sequence[PriceBar], period: int, *, adjustment_policy: PriceAdjustmentPolicy
) -> TechnicalSeries:
    _check_period(period)
    checked, values = _close(bars, adjustment_policy)
    return TechnicalSeries(
        _sma_values(values, period), str(checked[0].ticker) if checked else "", adjustment_policy
    )


def ema(
    bars: Sequence[PriceBar], period: int, *, adjustment_policy: PriceAdjustmentPolicy
) -> TechnicalSeries:
    _check_period(period)
    checked, values = _close(bars, adjustment_policy)
    out: list[Decimal | None] = [None] * len(values)
    if len(values) >= period:
        current = sum(values[:period], Decimal(0)) / period
        out[period - 1] = current
        alpha = Decimal(2) / (period + 1)
        for i in range(period, len(values)):
            current = values[i] * alpha + current * (Decimal(1) - alpha)
            out[i] = current
    return TechnicalSeries(tuple(out), str(checked[0].ticker) if checked else "", adjustment_policy)


def macd(
    bars: Sequence[PriceBar],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
    *,
    adjustment_policy: PriceAdjustmentPolicy,
) -> MACDResult:
    _check_period(fast_period)
    _check_period(slow_period)
    _check_period(signal_period)
    if fast_period >= slow_period:
        raise ValueError("fast_period must be less than slow_period")
    checked, values = _close(bars, adjustment_policy)
    fast, slow = (
        ema(checked, fast_period, adjustment_policy=adjustment_policy).values,
        ema(checked, slow_period, adjustment_policy=adjustment_policy).values,
    )
    line: list[Decimal | None] = [
        None if f is None or s is None else f - s for f, s in zip(fast, slow)
    ]
    signal: list[Decimal | None] = [None] * len(line)
    usable = [x for x in line if x is not None]
    if len(usable) >= signal_period:
        current = sum(usable[:signal_period], Decimal(0)) / signal_period
        first = next(i for i, x in enumerate(line) if x is not None) + signal_period - 1
        signal[first] = current
        alpha = Decimal(2) / (signal_period + 1)
        for i in range(first + 1, len(line)):
            line_value = line[i]
            if line_value is not None:
                current = line_value * alpha + current * (Decimal(1) - alpha)
                signal[i] = current
    histogram = tuple(
        None if line_value is None or signal_value is None else line_value - signal_value
        for line_value, signal_value in zip(line, signal)
    )
    return MACDResult(
        tuple(line),
        tuple(signal),
        histogram,
        str(checked[0].ticker) if checked else "",
        adjustment_policy,
    )


def rsi(
    bars: Sequence[PriceBar], period: int = 14, *, adjustment_policy: PriceAdjustmentPolicy
) -> TechnicalSeries:
    _check_period(period)
    checked, closes = _close(bars, adjustment_policy)
    out: list[Decimal | None] = [None] * len(closes)
    if len(closes) <= period:
        return TechnicalSeries(
            tuple(out), str(checked[0].ticker) if checked else "", adjustment_policy
        )
    gains = [max(d, Decimal(0)) for d in (closes[i] - closes[i - 1] for i in range(1, len(closes)))]
    losses = [
        max(-d, Decimal(0)) for d in (closes[i] - closes[i - 1] for i in range(1, len(closes)))
    ]
    avg_gain, avg_loss = (
        sum(gains[:period], Decimal(0)) / period,
        sum(losses[:period], Decimal(0)) / period,
    )

    def value() -> Decimal:
        if avg_gain == 0 and avg_loss == 0:
            return Decimal(50)
        return (
            Decimal(100)
            if avg_loss == 0
            else Decimal(100) - Decimal(100) / (Decimal(1) + avg_gain / avg_loss)
        )

    out[period] = value()
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        out[i + 1] = value()
    return TechnicalSeries(tuple(out), str(checked[0].ticker) if checked else "", adjustment_policy)


def atr(
    bars: Sequence[PriceBar], period: int = 14, *, adjustment_policy: PriceAdjustmentPolicy
) -> TechnicalSeries:
    _check_period(period)
    checked = _bars(bars, adjustment_policy)
    out: list[Decimal | None] = [None] * len(checked)
    if len(checked) <= period:
        return TechnicalSeries(
            tuple(out), str(checked[0].ticker) if checked else "", adjustment_policy
        )
    true_ranges = [
        max(b.high - b.low, abs(b.high - checked[i - 1].close), abs(b.low - checked[i - 1].close))
        for i, b in enumerate(checked)
        if i
    ]
    current = sum(true_ranges[:period], Decimal(0)) / period
    out[period] = current
    for i in range(period, len(true_ranges)):
        current = (current * (period - 1) + true_ranges[i]) / period
        out[i + 1] = current
    return TechnicalSeries(tuple(out), str(checked[0].ticker) if checked else "", adjustment_policy)


def bollinger_bands(
    bars: Sequence[PriceBar],
    period: int = 20,
    deviations: int = 2,
    *,
    adjustment_policy: PriceAdjustmentPolicy,
) -> tuple[Series, Series, Series]:
    _check_period(period)
    if deviations < 0:
        raise ValueError("deviations cannot be negative")
    checked, closes = _close(bars, adjustment_policy)
    middle: list[Decimal | None] = [None] * len(closes)
    upper = middle.copy()
    lower = middle.copy()
    for i in range(period - 1, len(closes)):
        window = closes[i + 1 - period : i + 1]
        mean = sum(window, Decimal(0)) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        spread = Decimal(str(deviations)) * Decimal(str(variance)).sqrt()
        middle[i], upper[i], lower[i] = mean, mean + spread, mean - spread
    return tuple(middle), tuple(upper), tuple(lower)


def rolling_volatility(
    bars: Sequence[PriceBar], period: int = 20, *, adjustment_policy: PriceAdjustmentPolicy
) -> TechnicalSeries:
    _check_period(period)
    checked, closes = _close(bars, adjustment_policy)
    returns: list[Decimal | None] = [
        None if closes[i - 1] == 0 else closes[i] / closes[i - 1] - 1
        for i in range(1, len(closes))
    ]
    out: list[Decimal | None] = [None] * len(closes)
    for i in range(period - 1, len(returns)):
        w = returns[i + 1 - period : i + 1]
        if any(value is None for value in w):
            continue
        numeric = [value for value in w if value is not None]
        mean = sum(numeric, Decimal(0)) / period
        variance = sum((x - mean) ** 2 for x in numeric) / period
        out[i + 1] = Decimal(str(variance)).sqrt()
    return TechnicalSeries(tuple(out), str(checked[0].ticker) if checked else "", adjustment_policy)


def drawdown(
    bars: Sequence[PriceBar], *, adjustment_policy: PriceAdjustmentPolicy
) -> TechnicalSeries:
    checked, closes = _close(bars, adjustment_policy)
    out: list[Decimal | None] = []
    peak: Decimal | None = None
    for close in closes:
        peak = close if peak is None or close > peak else peak
        out.append(Decimal(0) if peak == 0 else close / peak - 1)
    return TechnicalSeries(tuple(out), str(checked[0].ticker) if checked else "", adjustment_policy)


def momentum(
    bars: Sequence[PriceBar], period: int = 10, *, adjustment_policy: PriceAdjustmentPolicy
) -> TechnicalSeries:
    _check_period(period)
    checked, closes = _close(bars, adjustment_policy)
    return TechnicalSeries(
        tuple(
            None
            if i < period or closes[i - period] == 0
            else closes[i] / closes[i - period] - 1
            for i in range(len(closes))
        ),
        str(checked[0].ticker) if checked else "",
        adjustment_policy,
    )


def relative_strength(
    bars: Sequence[PriceBar],
    benchmark: Sequence[PriceBar],
    *,
    adjustment_policy: PriceAdjustmentPolicy,
) -> TechnicalSeries:
    left, a = _close(bars, adjustment_policy)
    right, b = _close(benchmark, adjustment_policy)
    if len(a) != len(b) or tuple(x.session for x in left) != tuple(x.session for x in right):
        raise ValueError("series must have matching sessions")
    return TechnicalSeries(
        tuple(x / y if y else None for x, y in zip(a, b)),
        str(left[0].ticker) if left else "",
        adjustment_policy,
    )


def classify_trend(
    bars: Sequence[PriceBar],
    period: int = 20,
    *,
    adjustment_policy: PriceAdjustmentPolicy,
    flat_tolerance: Decimal = Decimal("0"),
) -> Trend:
    _check_period(period)
    _, closes = _close(bars, adjustment_policy)
    if len(closes) < period:
        return Trend.INSUFFICIENT_DATA
    change = closes[-1] / closes[-period] - 1
    if abs(change) <= flat_tolerance:
        return Trend.FLAT
    return Trend.UP if change > 0 else Trend.DOWN


# Familiar aliases for callers migrating from the legacy names.
SMA, EMA, MACD, RSI, ATR = sma, ema, macd, rsi, atr
BollingerBands = bollinger_bands
RollingVolatility = rolling_volatility
Drawdown = drawdown
Momentum = momentum
RelativeStrength = relative_strength
TrendClassification = classify_trend
