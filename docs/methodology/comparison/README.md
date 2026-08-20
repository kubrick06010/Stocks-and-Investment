# Strategy comparison V1

Comparisons use persisted runs and identity-keyed rankings. Top-N overlap is
intersection divided by N; Jaccard is intersection divided by union. Rank
correlation is Spearman over common symbols only. Incompatible universe or
date assumptions are returned as explicit mismatches.

## Fairness closure matrix

`compare_backtests` consumes immutable `BacktestRun` objects. It never reruns a
strategy or fetches data. A performance comparison is compatible only when the
following `BacktestConfigV1` fields agree:

- period (`start`, `end`)
- historical universe/cohort identity
- benchmark
- rebalance frequency
- selection rule
- `top_n`
- weighting method
- transaction-cost model
- transaction-cost rate
- corporate-action policy
- return convention

Strategy name and version are also retained as identity. If the strategy name
is equal but its version differs, `strategy_version` is reported as a mismatch;
versions are never collapsed.

The comparison tests change exactly one represented field at a time and include
a hand-checked compatible pair. Mismatch details retain both values so a caller
can explain why performance was not compared as a fair head-to-head result.
When any mismatch exists, top-level direct performance fields are `None`; the
individual diagnostic metrics remain available only as explicitly non-
comparable metadata. This prevents an incompatible pair from masquerading as a
valid winner.

The lead integrator approved the concrete contract request discovered during
closure. `BacktestConfigV1` now persists universe, rebalance frequency,
transaction-cost model, and return convention. The simulator still executes
only equal-weight formation, while the comparison contract can faithfully
identify persisted runs produced with a different weighting methodology.
