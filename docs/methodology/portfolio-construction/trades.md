# E4C — Target/current trade reconciliation

`reconcile_target_trades` is a pure estimate of a funded rebalance. It does
not fetch prices, call storage, mutate a ledger, or run a strategy.

## Identity and alignment

The calculation uses the union of ticker symbols in the current and target
maps. Every result is keyed by its `TradeEstimate.ticker` and returned in
symbol order. No positional lists or `zip` alignment are used. Duplicate
case-insensitive ticker identities are rejected.

## Economics

Weights are fractions of pre-trade capital. For ticker `s`:

```text
target_value_s = capital × target_weight_s
traded_notional_s = capital × |target_weight_s - current_weight_s|
```

Gross traded notional is the sum of every ticker's traded notional, so it
counts both buys and sells. Turnover is:

```text
turnover = gross_traded_notional / capital_before
```

The cost model is explicitly:

```text
estimated_transaction_cost = gross_traded_notional × transaction_cost_rate
```

Cash is reconciled as:

```text
cash_after = capital_before - invested_after - estimated_transaction_cost
```

where `invested_after = capital_before × sum(target_weights)`. A negative
cash result is rejected; the function never creates leverage or silently clips
the target. This means a fully invested target with non-zero costs requires an
explicit cash buffer in the target weights (or a later construction policy
that defines post-cost scaling).

Zero turnover produces zero cost. Partial turnover charges only changed
tickers. The function rejects non-finite values, invalid weights, invalid
capital, invalid rates, and inconsistent cash.
