# Wave E4 data flow

```text
persisted ResearchRun + ResearchResults
                 |
                 v
 versioned construction policy + current weights
                 |
                 v
 deterministic targets / constraints / trades / costs
                 |
       +---------+---------+
       v                   v
  backtest target      optional ledger transaction plan
  (simulation)         (never automatic execution)
```

Portfolio analytics remain read-only consumers of realized portfolio state.
The ledger remains the accounting source of truth. Construction output is a
proposal, not a transaction or recommendation.
