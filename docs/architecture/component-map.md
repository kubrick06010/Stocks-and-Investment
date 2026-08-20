# V2 component map

```text
interfaces/  <- provider, storage, calculation, strategy protocols
domain/      <- immutable instruments, market records, periods, observations, scores, runs, ledger
data/        -> normalized observations + raw cache
provenance/  -> source/filing/retrieval/derivation metadata and PIT gates
storage/     -> SQLite repositories and migrations
fundamentals/ technical/ -> pure calculators over domain observations
strategies/ scoring/ screening/ -> explainable research decisions
thesis/      -> deterministic narrative from structured results
portfolio/ analytics/ -> ledger, valuation, returns, benchmark comparison
backtesting/ -> PIT snapshots + portfolio simulation
cli/         -> formatting/orchestration only
```
