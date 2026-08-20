from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from stocks_investment.domain import DataProvenance, PriceAdjustmentPolicy, PriceBar, Ticker
from stocks_investment.technical import (
    Trend,
    atr,
    bollinger_bands,
    classify_trend,
    drawdown,
    ema,
    macd,
    momentum,
    relative_strength,
    rolling_volatility,
    rsi,
    sma,
)


def bars(values, *, policy=PriceAdjustmentPolicy.SPLIT_ADJUSTED, start=1, ticker="AAA"):
    provenance = DataProvenance(
        "test", "test", datetime(2025, 1, 1, tzinfo=timezone.utc), date(2025, 1, 1)
    )
    sessions = []
    current = date(2025, 1, start)
    for _ in values:
        while current.weekday() >= 5:
            current += timedelta(days=1)
        sessions.append(current)
        current += timedelta(days=1)
    return tuple(
        PriceBar(
            Ticker(ticker),
            session,
            Decimal(str(v)),
            Decimal(str(v)),
            Decimal(str(v)),
            Decimal(str(v)),
            None,
            "USD",
            policy,
            provenance,
        )
        for session, v in zip(sessions, values)
    )


def test_policy_is_explicit_and_mixed_or_wrong_policy_is_rejected():
    series = bars([1, 2, 3])
    with pytest.raises(TypeError):
        sma(series, 2)  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        sma(series, 2, adjustment_policy=PriceAdjustmentPolicy.RAW)
    with pytest.raises(ValueError):
        sma(
            series[:1] + bars([4], start=4, policy=PriceAdjustmentPolicy.RAW),
            2,
            adjustment_policy=PriceAdjustmentPolicy.SPLIT_ADJUSTED,
        )


def test_sma_ema_and_macd_are_aligned_and_do_not_pad_missing_with_zero():
    series = bars([1, 2, 3, 4, 5])
    assert sma(series, 3, adjustment_policy=PriceAdjustmentPolicy.SPLIT_ADJUSTED).values[:2] == (
        None,
        None,
    )
    assert ema(series, 3, adjustment_policy=PriceAdjustmentPolicy.SPLIT_ADJUSTED).values[:2] == (
        None,
        None,
    )
    result = macd(series, 2, 3, 2, adjustment_policy=PriceAdjustmentPolicy.SPLIT_ADJUSTED)
    assert result.line[:2] == (None, None)
    assert result.signal[:3] == (None, None, None)


def test_flat_series_has_neutral_rsi_and_zero_risk_measures():
    series = bars([10] * 20)
    assert rsi(series, 5, adjustment_policy=PriceAdjustmentPolicy.SPLIT_ADJUSTED).values[-1] == 50
    assert atr(series, 5, adjustment_policy=PriceAdjustmentPolicy.SPLIT_ADJUSTED).values[-1] == 0
    assert (
        rolling_volatility(
            series, 5, adjustment_policy=PriceAdjustmentPolicy.SPLIT_ADJUSTED
        ).values[-1]
        == 0
    )
    assert drawdown(series, adjustment_policy=PriceAdjustmentPolicy.SPLIT_ADJUSTED).values[-1] == 0
    assert (
        classify_trend(series, 5, adjustment_policy=PriceAdjustmentPolicy.SPLIT_ADJUSTED)
        is Trend.FLAT
    )


def test_split_adjusted_prices_are_consumed_as_given_without_silent_readjustment():
    series = bars([100, 50, 51], policy=PriceAdjustmentPolicy.SPLIT_ADJUSTED)
    assert sma(series, 2, adjustment_policy=PriceAdjustmentPolicy.SPLIT_ADJUSTED).values[
        -1
    ] == Decimal("50.5")
    with pytest.raises(ValueError):
        relative_strength(series, bars([1, 2, 3]), adjustment_policy=PriceAdjustmentPolicy.RAW)


def test_bollinger_momentum_and_relative_strength():
    series = bars([1, 2, 3, 4, 5])
    middle, upper, lower = bollinger_bands(
        series, 3, adjustment_policy=PriceAdjustmentPolicy.SPLIT_ADJUSTED
    )
    assert middle[:2] == (None, None) and upper[2] is not None and lower[2] is not None
    assert momentum(series, 2, adjustment_policy=PriceAdjustmentPolicy.SPLIT_ADJUSTED).values[
        2
    ] == Decimal("2")
    assert (
        relative_strength(
            series, bars([1, 1, 1, 1, 1]), adjustment_policy=PriceAdjustmentPolicy.SPLIT_ADJUSTED
        ).values[-1]
        == 5
    )


def test_weekend_and_nan_inputs_are_rejected():
    weekend = (replace(bars([1])[0], session=date(2025, 1, 4)),)  # 2025-01-04
    with pytest.raises(ValueError, match="weekend"):
        sma(weekend, 1, adjustment_policy=PriceAdjustmentPolicy.SPLIT_ADJUSTED)
    with pytest.raises(Exception):
        bars(["NaN"])


def test_short_series_returns_warmup_missing_values():
    series = bars([1, 2])
    assert atr(series, 14, adjustment_policy=PriceAdjustmentPolicy.SPLIT_ADJUSTED).values == (
        None,
        None,
    )
    assert (
        classify_trend(series, 14, adjustment_policy=PriceAdjustmentPolicy.SPLIT_ADJUSTED)
        is Trend.INSUFFICIENT_DATA
    )
