# Deterministic portfolio constructor V1

`deterministic_portfolio_constructor_v1` converts the exact persisted
`ResearchResult` identities named by a `PortfolioConstructionRequest` into a
target allocation. It does not rerun screening, fetch prices, query providers,
or infer a newer research state.

## Information and identity checks

Construction requires a completed `ResearchRun`, an exact request/run/as-of
match, the exact policy name and version, and every requested result. Supplied
results from another run, missing result IDs, or an as-of mismatch produce an
explicit `INSUFFICIENT_DATA` result. Input ordering never determines security
identity.

## Allocation sequence

1. Treat the result IDs frozen in the request as the eligible set.
2. Build equal or score-proportional base weights from their persisted scores.
3. Apply the versioned long-only, position, sector, cash, and turnover rules.
4. Reconcile current and target weights over the union of ticker identities.
5. Charge `gross_traded_notional × transaction_cost_rate`.

Target security weights and `cash_weight` are pre-cost allocation weights and
sum to one for a valid result. Costs are reported separately and funded from
the explicit target cash allocation. If the cash allocation cannot fund the
estimated cost, construction is `INFEASIBLE`; V1 never creates leverage,
silently clips a holding, or treats fees as free.

For example, a 98% risky allocation and 2% target cash on $100,000 with
$98 estimated costs has $1,902 economic cash after costs:

```text
$100,000 - $98,000 invested - $98 costs = $1,902 cash after costs
```

## Deliberate V1 limits

- Fractional-share permission is persisted but share rounding/execution is not
  performed; construction remains weight/notional based.
- Sector caps require an externally supplied, point-in-time sector map. The
  frozen constructor request does not yet carry such a snapshot, so an engine
  request using a sector cap fails explicitly rather than using current sector
  data.
- A hard turnover cap rejects a violating target. V1 does not optimize toward
  the nearest lower-turnover portfolio.
- No covariance optimizer, volatility targeting, leverage, shorting, minimum
  trade size, or liquidity model is implemented.
- A construction result is an inspectable target and estimate, not a mutation
  of the validated transaction ledger.
