"""Immutable inputs and outputs for portfolio accounting."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Mapping


ZERO = Decimal("0")


class TransactionType(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    DIVIDEND = "DIVIDEND"
    FEE = "FEE"
    TAX = "TAX"
    SPLIT = "SPLIT"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    CASH_DEPOSIT = "CASH_DEPOSIT"
    CASH_WITHDRAWAL = "CASH_WITHDRAWAL"


def _decimal(value: Decimal | int | float | str | None, default: Decimal = ZERO) -> Decimal:
    return default if value is None else Decimal(str(value))


@dataclass(frozen=True, slots=True)
class Transaction:
    """A normalized accounting event.  Monetary values are in ``currency``."""

    id: str
    date: date
    type: TransactionType
    currency: str = ""
    symbol: str | None = None
    quantity: Decimal = ZERO
    price: Decimal = ZERO
    amount: Decimal | None = None
    amount_per_share: Decimal | None = None
    fee: Decimal = ZERO
    fee_currency: str | None = None
    split_numerator: int | None = None
    split_denominator: int | None = None
    unit_cost: Decimal | None = None
    occurred_at: datetime | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "type", TransactionType(self.type))
        object.__setattr__(self, "currency", self.currency.upper().strip())
        if self.symbol is not None:
            object.__setattr__(self, "symbol", self.symbol.upper().strip())
        for name in ("quantity", "price", "fee"):
            object.__setattr__(self, name, _decimal(getattr(self, name)))
        if self.amount is not None:
            object.__setattr__(self, "amount", _decimal(self.amount))
        if self.amount_per_share is not None:
            object.__setattr__(self, "amount_per_share", _decimal(self.amount_per_share))
        if self.unit_cost is not None:
            object.__setattr__(self, "unit_cost", _decimal(self.unit_cost))
        if not self.id.strip():
            raise ValueError("transaction id must not be empty")
        if self.type in (TransactionType.CASH_DEPOSIT, TransactionType.CASH_WITHDRAWAL, TransactionType.FEE, TransactionType.TAX) and not self.currency:
            raise ValueError(f"{self.type} requires a currency")
        if self.type in (TransactionType.BUY, TransactionType.SELL, TransactionType.DIVIDEND, TransactionType.SPLIT, TransactionType.TRANSFER_IN, TransactionType.TRANSFER_OUT) and not self.symbol:
            raise ValueError(f"{self.type} requires a symbol")
        if self.quantity < 0 or self.price < 0 or self.fee < 0:
            raise ValueError("quantity, price, and fee cannot be negative")
        if self.amount is not None and self.amount < 0:
            raise ValueError("amount cannot be negative")
        if self.amount_per_share is not None and self.amount_per_share < 0:
            raise ValueError("amount_per_share cannot be negative")
        if self.type is TransactionType.SPLIT:
            if not self.split_numerator or not self.split_denominator or self.split_numerator <= 0 or self.split_denominator <= 0:
                raise ValueError("SPLIT requires positive split_numerator and split_denominator")

    @property
    def total(self) -> Decimal:
        if self.amount is not None:
            return self.amount
        per_share = self.amount_per_share if self.amount_per_share is not None else self.price
        return self.quantity * per_share


@dataclass(frozen=True, slots=True)
class Lot:
    quantity: Decimal
    cost_basis: Decimal
    currency: str

    @property
    def unit_cost(self) -> Decimal:
        return self.cost_basis / self.quantity if self.quantity else ZERO


@dataclass(frozen=True, slots=True)
class Position:
    symbol: str
    quantity: Decimal
    cost_basis: Decimal
    currency: str
    realized_pnl: Decimal = ZERO
    market_price: Decimal | None = None

    @property
    def average_cost(self) -> Decimal:
        return self.cost_basis / self.quantity if self.quantity else ZERO

    @property
    def market_value(self) -> Decimal | None:
        return None if self.market_price is None else self.quantity * self.market_price

    @property
    def unrealized_pnl(self) -> Decimal | None:
        value = self.market_value
        return None if value is None else value - self.cost_basis


@dataclass(frozen=True, slots=True)
class CashBalance:
    currency: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class PortfolioState:
    as_of: date | None
    cash: Mapping[str, Decimal]
    positions: Mapping[str, Position]
    realized_pnl: Decimal
    total_cost_basis: Decimal
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    total_value: Decimal | None

    @property
    def cash_balances(self) -> tuple[CashBalance, ...]:
        return tuple(CashBalance(currency, amount) for currency, amount in sorted(self.cash.items()))


PortfolioReport = PortfolioState
