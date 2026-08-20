"""Canonical market-domain records shared by providers and consumers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from stocks_investment.domain.models import DataProvenance, Ticker


class PriceAdjustmentPolicy(StrEnum):
    RAW = "raw"
    SPLIT_ADJUSTED = "split_adjusted"
    TOTAL_RETURN_ADJUSTED = "total_return_adjusted"
    PROVIDER_ADJUSTED = "provider_adjusted"


@dataclass(frozen=True, slots=True)
class PriceBar:
    ticker: Ticker
    session: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int | None
    currency: str
    adjustment_policy: PriceAdjustmentPolicy
    provenance: DataProvenance

    def __post_init__(self) -> None:
        if min(self.open, self.high, self.low, self.close) < 0:
            raise ValueError("price values cannot be negative")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("OHLC values are internally inconsistent")
        if self.volume is not None and self.volume < 0:
            raise ValueError("volume cannot be negative")


@dataclass(frozen=True, slots=True)
class Quote:
    ticker: Ticker
    price: Decimal
    observed_at: datetime
    currency: str
    provenance: DataProvenance

    def __post_init__(self) -> None:
        if self.price < 0:
            raise ValueError("quote price cannot be negative")


@dataclass(frozen=True, slots=True)
class DividendAction:
    ticker: Ticker
    ex_date: date
    amount_per_share: Decimal
    currency: str
    provenance: DataProvenance

    def __post_init__(self) -> None:
        if self.amount_per_share <= 0:
            raise ValueError("dividend amount_per_share must be positive")


@dataclass(frozen=True, slots=True)
class SplitAction:
    ticker: Ticker
    ex_date: date
    numerator: int
    denominator: int
    provenance: DataProvenance

    def __post_init__(self) -> None:
        if self.numerator <= 0 or self.denominator <= 0:
            raise ValueError("split ratio values must be positive")

    @property
    def factor(self) -> Decimal:
        return Decimal(self.numerator) / Decimal(self.denominator)


@dataclass(frozen=True, slots=True)
class SpinoffAction:
    ticker: Ticker
    ex_date: date
    distributed_symbol: Ticker
    distribution_ratio: Decimal
    provenance: DataProvenance

    def __post_init__(self) -> None:
        if self.distribution_ratio <= 0:
            raise ValueError("spinoff distribution_ratio must be positive")


CorporateAction = DividendAction | SplitAction | SpinoffAction
