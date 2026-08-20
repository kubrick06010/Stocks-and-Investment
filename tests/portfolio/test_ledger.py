from datetime import date
from decimal import Decimal

import pytest

from stocks_investment.portfolio import PortfolioLedger, Transaction


def tx(id_, day, kind, **kwargs):
    return Transaction(id=id_, date=date.fromisoformat(day), type=kind, **kwargs)


def test_deposit_buy_dividend_split_partial_sell_fee_report():
    ledger = PortfolioLedger([
        tx("deposit", "2025-01-01", "CASH_DEPOSIT", currency="USD", amount="10000"),
        tx("buy", "2025-01-02", "BUY", symbol="acme", currency="USD", quantity="100", price="50", fee="10"),
        tx("dividend", "2025-02-01", "DIVIDEND", symbol="ACME", currency="USD", quantity="100", price="0.50"),
        tx("split", "2025-03-01", "SPLIT", symbol="ACME", currency="USD", split_numerator=2, split_denominator=1),
        tx("sell", "2025-04-01", "SELL", symbol="ACME", currency="USD", quantity="50", price="60"),
        tx("fee", "2025-04-02", "FEE", currency="USD", amount="5"),
    ])

    state = ledger.reconstruct(prices={"ACME": "55"})
    position = state.positions["ACME"]
    assert position.quantity == Decimal("150")
    assert position.cost_basis == Decimal("3757.50")
    assert position.average_cost == Decimal("25.05")
    assert position.realized_pnl == Decimal("1747.50")
    assert position.market_value == Decimal("8250")
    assert position.unrealized_pnl == Decimal("4492.50")
    assert state.cash["USD"] == Decimal("8035")
    assert state.realized_pnl == Decimal("1747.50")
    assert state.total_value == Decimal("16285")


def test_fifo_cost_basis_and_transfer_events():
    ledger = PortfolioLedger([
        tx("d", "2025-01-01", "CASH_DEPOSIT", currency="EUR", amount="1000"),
        tx("b1", "2025-01-02", "BUY", symbol="ETF", currency="EUR", quantity="1.5", price="100"),
        tx("b2", "2025-01-03", "BUY", symbol="ETF", currency="EUR", quantity="2", price="200"),
        tx("out", "2025-01-04", "TRANSFER_OUT", symbol="ETF", currency="EUR", quantity="1"),
        tx("in", "2025-01-05", "TRANSFER_IN", symbol="ETF", currency="EUR", quantity="0.5", unit_cost="250"),
        tx("s", "2025-01-06", "SELL", symbol="ETF", currency="EUR", quantity="1", price="300"),
    ])
    state = ledger.reconstruct()
    assert state.positions["ETF"].quantity == Decimal("2")
    assert state.positions["ETF"].cost_basis == Decimal("425")
    assert state.realized_pnl == Decimal("150")


def test_cash_and_position_currencies_are_independent():
    ledger = PortfolioLedger([
        tx("usd", "2025-01-01", "CASH_DEPOSIT", currency="USD", amount="1000"),
        tx("eur", "2025-01-01", "CASH_DEPOSIT", currency="EUR", amount="500"),
        tx("buy", "2025-01-02", "BUY", symbol="EU", currency="EUR", quantity="2", price="100"),
    ])
    state = ledger.reconstruct()
    assert state.cash == {"USD": Decimal("1000"), "EUR": Decimal("300")}
    assert state.positions["EU"].currency == "EUR"


def test_negative_cash_and_duplicate_ids_are_rejected():
    with pytest.raises(ValueError, match="insufficient USD cash"):
        PortfolioLedger([tx("b", "2025-01-01", "BUY", symbol="A", currency="USD", quantity=1, price=10)]).reconstruct()
    with pytest.raises(ValueError, match="duplicate transaction id"):
        PortfolioLedger([tx("d", "2025-01-01", "CASH_DEPOSIT", currency="USD", amount=1), tx("d", "2025-01-02", "CASH_DEPOSIT", currency="USD", amount=1)])
