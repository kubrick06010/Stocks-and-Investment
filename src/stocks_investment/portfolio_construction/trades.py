"""Identity-safe target/current trade reconciliation.

This module deliberately contains no provider, storage, ledger, or backtest
integration.  It estimates a fully funded rebalance from portfolio weights.
Weights are measured against the pre-trade capital; transaction costs are
charged on gross traded notional (buys plus sells).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from stocks_investment.domain.portfolio_construction import TradeEstimate
from stocks_investment.domain.models import Ticker


@dataclass(frozen=True, slots=True)
class TradeReconciliation:
    """Complete, deterministic result of a target-vs-current reconciliation."""

    trades: tuple[TradeEstimate, ...]
    gross_traded_notional: float
    turnover: float
    estimated_transaction_cost: float
    capital_before: float
    invested_after: float
    cash_after: float

    def __post_init__(self) -> None:
        values = (
            self.gross_traded_notional,
            self.turnover,
            self.estimated_transaction_cost,
            self.capital_before,
            self.invested_after,
            self.cash_after,
        )
        if not all(isfinite(value) for value in values):
            raise ValueError("trade reconciliation values must be finite")
        if self.capital_before <= 0:
            raise ValueError("capital_before must be positive")
        if min(self.gross_traded_notional, self.turnover,
               self.estimated_transaction_cost, self.invested_after,
               self.cash_after) < -1e-9:
            raise ValueError("trade reconciliation cannot contain negative money")
        if abs(self.gross_traded_notional - sum(item.traded_notional for item in self.trades)) > 1e-8:
            raise ValueError("gross traded notional does not reconcile with trades")
        if abs(self.estimated_transaction_cost - sum(item.estimated_cost for item in self.trades)) > 1e-8:
            raise ValueError("estimated cost does not reconcile with trades")
        if abs(self.capital_before - self.invested_after - self.cash_after - self.estimated_transaction_cost) > 1e-8:
            raise ValueError("capital and cash do not reconcile")


def _symbol_key(key: object) -> str:
    symbol = getattr(key, "symbol", key)
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("trade keys must be non-empty ticker symbols")
    return symbol.strip().upper()


def _normalise_weights(weights: Mapping[object, float], name: str) -> dict[str, float]:
    normalised: dict[str, float] = {}
    for key, value in weights.items():
        symbol = _symbol_key(key)
        if symbol in normalised:
            raise ValueError(f"duplicate ticker identity in {name}: {symbol}")
        if not isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"{name} weights must be finite and in 0..1")
        normalised[symbol] = float(value)
    if sum(normalised.values()) > 1 + 1e-9:
        raise ValueError(f"{name} weights cannot exceed 100%")
    return normalised


def reconcile_target_trades(
    current_weights: Mapping[object, float],
    target_weights: Mapping[object, float],
    capital: float,
    transaction_cost_rate: float,
) -> TradeReconciliation:
    """Reconcile weights using the ticker-keyed union of both portfolios.

    ``gross_traded_notional`` is the sum of all absolute dollar changes,
    therefore it counts buys and sells.  ``turnover`` is that amount divided
    by pre-trade capital.  Costs are ``gross_traded_notional * rate``.

    Target security values use pre-trade capital.  The residual is target cash
    less costs, so a target requiring more cash than available fails explicitly
    instead of creating leverage or silently clipping a position.
    """
    if not isfinite(capital) or capital <= 0:
        raise ValueError("capital must be finite and positive")
    if not isfinite(transaction_cost_rate) or not 0 <= transaction_cost_rate < 1:
        raise ValueError("transaction_cost_rate must be finite and in [0, 1)")

    current = _normalise_weights(current_weights, "current")
    target = _normalise_weights(target_weights, "target")
    symbols = sorted(set(current) | set(target))
    trades: list[TradeEstimate] = []
    for symbol in symbols:
        before = current.get(symbol, 0.0)
        after = target.get(symbol, 0.0)
        delta = after - before
        notional = abs(delta) * capital
        cost = notional * transaction_cost_rate
        trades.append(TradeEstimate(
            ticker=_ticker(symbol),
            current_weight=before,
            target_weight=after,
            weight_delta=delta,
            traded_notional=notional,
            estimated_cost=cost,
        ))

    gross = sum(item.traded_notional for item in trades)
    cost = gross * transaction_cost_rate
    invested = capital * sum(target.values())
    cash = capital - invested - cost
    if cash < -1e-9:
        raise ValueError("target allocation and transaction costs require negative cash")
    return TradeReconciliation(
        trades=tuple(trades),
        gross_traded_notional=gross,
        turnover=gross / capital,
        estimated_transaction_cost=cost,
        capital_before=capital,
        invested_after=invested,
        cash_after=max(0.0, cash),
    )


def _ticker(symbol: str) -> Ticker:
    return Ticker(symbol)
