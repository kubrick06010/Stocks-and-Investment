# E4A base weighting

This module is a pure mechanical boundary from persisted `ResearchResult`
records to security-keyed target weights. It does not fetch prices or
fundamentals, rerun a strategy, apply portfolio constraints, optimize, or
mutate a ledger.

## Eligibility

Eligibility is an explicit caller choice:

- `selected`: positive persisted rank and `classification == "selected"`;
- `ranked`: any result with a positive persisted rank, regardless of its
  classification.

Every supplied result must belong to the exact requested `run_id`. A mismatched
run or duplicate ticker is an error; neither is silently discarded.

## Methods

`equal_weight` assigns `1/N` to each eligible ticker. It deliberately does not
require a score.

`score_proportional` assigns:

```text
weight_i = composite_score_i / sum(composite_scores)
```

This method requires every eligible score to be finite and strictly positive.
Missing, zero, negative, or non-finite scores produce an explicit
`insufficient_data` result with no partial allocation. No invalid score is
coerced to zero.

Targets are always sorted by ticker symbol, so allocation cannot depend on
input ordering. Each target retains its source result ID and score for later
integration with the portfolio construction contract.

## Scope boundary

The result is intentionally an internal, typed intermediate. Cash, constraints,
turnover, transaction costs, shares, prices, corporate actions, and ledger
transactions belong to later E4 workstreams.
