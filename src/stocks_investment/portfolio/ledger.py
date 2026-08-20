"""Deterministic FIFO reconstruction of portfolio state from ledger events."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Mapping

from stocks_investment.portfolio.models import Lot, Position, PortfolioState, Transaction, TransactionType, ZERO


@dataclass
class _MutablePosition:
    lots: list[Lot]
    realized: Decimal = ZERO


class PortfolioLedger:
    """Append-only transaction ledger with FIFO lot reconstruction.

    Cash and position currencies are kept separate.  ``prices`` and ``fx_rates``
    are optional valuation inputs and never alter accounting cost basis.
    """

    def __init__(self, transactions: Iterable[Transaction] = ()) -> None:
        self._transactions: list[Transaction] = []
        self.extend(transactions)

    @property
    def transactions(self) -> tuple[Transaction, ...]:
        return tuple(self._transactions)

    def add(self, transaction: Transaction) -> None:
        if any(item.id == transaction.id for item in self._transactions):
            raise ValueError(f"duplicate transaction id: {transaction.id}")
        self._transactions.append(transaction)
        self._transactions.sort(key=lambda item: (item.date, item.occurred_at or item.date, item.id))

    def extend(self, transactions: Iterable[Transaction]) -> None:
        for transaction in transactions:
            self.add(transaction)

    def reconstruct(
        self,
        as_of: date | None = None,
        prices: Mapping[str, Decimal | int | float | str] | None = None,
        fx_rates: Mapping[str, Decimal | int | float | str] | None = None,
    ) -> PortfolioState:
        cash: defaultdict[str, Decimal] = defaultdict(Decimal)
        positions: dict[str, _MutablePosition] = {}
        for tx in self._transactions:
            if as_of is not None and tx.date > as_of:
                break
            self._apply(tx, cash, positions)

        result: dict[str, Position] = {}
        market_value = ZERO
        has_market_value = bool(prices)
        for symbol, state in positions.items():
            quantity = sum((lot.quantity for lot in state.lots), ZERO)
            cost = sum((lot.cost_basis for lot in state.lots), ZERO)
            if not quantity:
                continue
            currency = state.lots[0].currency
            price = Decimal(str(prices[symbol])) if prices and symbol in prices else None
            result[symbol] = Position(symbol, quantity, cost, currency, state.realized, price)
            if price is not None:
                market_value += quantity * price
        realized = sum((state.realized for state in positions.values()), ZERO)
        cost_basis = sum((position.cost_basis for position in result.values()), ZERO)
        unrealized = market_value - cost_basis if has_market_value else None
        cash_total = sum(cash.values(), ZERO)
        total_value = cash_total + market_value if has_market_value else None
        # FX rates are intentionally only a valuation conversion hook.  Without a
        # reporting currency, preserving native currency values is less surprising.
        _ = fx_rates
        return PortfolioState(as_of, dict(cash), result, realized, cost_basis, market_value if has_market_value else None, unrealized, total_value)

    @staticmethod
    def _apply(tx: Transaction, cash: defaultdict[str, Decimal], positions: dict[str, _MutablePosition]) -> None:
        kind = tx.type
        if kind is TransactionType.CASH_DEPOSIT:
            cash[tx.currency] += tx.total
        elif kind is TransactionType.CASH_WITHDRAWAL:
            PortfolioLedger._debit_cash(cash, tx.currency, tx.total)
        elif kind in (TransactionType.FEE, TransactionType.TAX):
            PortfolioLedger._debit_cash(cash, tx.currency, tx.total)
        elif kind is TransactionType.BUY:
            PortfolioLedger._debit_cash(cash, tx.currency, tx.total)
            PortfolioLedger._debit_cash(cash, tx.fee_currency or tx.currency, tx.fee)
            PortfolioLedger._add_lot(positions, tx.symbol or "", tx.quantity, tx.total + tx.fee, tx.currency)
        elif kind is TransactionType.SELL:
            state = PortfolioLedger._state(positions, tx.symbol or "")
            proceeds = tx.total
            cost = PortfolioLedger._remove_lots(state, tx.quantity)
            state.realized += proceeds - cost - tx.fee
            cash[tx.currency] += proceeds
            PortfolioLedger._debit_cash(cash, tx.fee_currency or tx.currency, tx.fee)
        elif kind is TransactionType.DIVIDEND:
            cash[tx.currency] += tx.total
        elif kind is TransactionType.SPLIT:
            state = PortfolioLedger._state(positions, tx.symbol or "")
            factor = Decimal(tx.split_numerator or 0) / Decimal(tx.split_denominator or 1)
            state.lots[:] = [Lot(lot.quantity * factor, lot.cost_basis, lot.currency) for lot in state.lots]
        elif kind is TransactionType.TRANSFER_IN:
            cost = tx.amount if tx.amount is not None else tx.quantity * (tx.unit_cost or tx.price)
            PortfolioLedger._add_lot(positions, tx.symbol or "", tx.quantity, cost, tx.currency)
        elif kind is TransactionType.TRANSFER_OUT:
            PortfolioLedger._remove_lots(PortfolioLedger._state(positions, tx.symbol or ""), tx.quantity)

    @staticmethod
    def _state(positions: dict[str, _MutablePosition], symbol: str) -> _MutablePosition:
        return positions.setdefault(symbol, _MutablePosition([]))

    @staticmethod
    def _add_lot(positions: dict[str, _MutablePosition], symbol: str, quantity: Decimal, cost: Decimal, currency: str) -> None:
        if quantity <= 0:
            raise ValueError("transaction quantity must be positive for a position event")
        PortfolioLedger._state(positions, symbol).lots.append(Lot(quantity, cost, currency))

    @staticmethod
    def _remove_lots(state: _MutablePosition, quantity: Decimal) -> Decimal:
        if quantity <= 0:
            raise ValueError("transaction quantity must be positive when reducing a position")
        remaining, cost = quantity, ZERO
        while remaining:
            if not state.lots:
                raise ValueError("transaction would make a position negative")
            lot = state.lots[0]
            taken = min(remaining, lot.quantity)
            cost += taken * lot.unit_cost
            remaining -= taken
            if taken == lot.quantity:
                state.lots.pop(0)
            else:
                state.lots[0] = Lot(lot.quantity - taken, lot.cost_basis - taken * lot.unit_cost, lot.currency)
        return cost

    @staticmethod
    def _debit_cash(cash: defaultdict[str, Decimal], currency: str, amount: Decimal) -> None:
        if amount < 0:
            raise ValueError("cash debit cannot be negative")
        if cash[currency] < amount:
            raise ValueError(f"insufficient {currency} cash")
        cash[currency] -= amount
