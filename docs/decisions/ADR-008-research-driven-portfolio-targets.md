# ADR-008: Research-driven portfolio targets remain separate from accounting

Status: Accepted for Wave E4 contract freeze.

## Decision

Portfolio construction consumes immutable ResearchRuns/ResearchResults and
produces versioned target weights, constraint evaluations and trade/cost
estimates. It does not modify scores, execute transactions or mutate the
portfolio ledger. Ticker identity and money reconciliation are mandatory.

## Consequences

- construction methodology can be backtested without rewriting signals;
- infeasible constraints remain visible rather than silently relaxed;
- turnover and expected costs are first-class;
- equal/score-proportional V1 remains transparent;
- covariance optimizers, leverage and automatic execution are deferred.
