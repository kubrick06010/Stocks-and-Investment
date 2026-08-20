# Factor efficacy V1

Efficacy joins persisted factor scores at research date with later outcomes.
It reports coverage, mean/median, quantile spread, Spearman rank IC and hit
rate. Small samples return an explicit insufficient-sample status. Overlapping
forward horizons may not be independent; no significance claims are made.

Every input observation is persisted with factor version, historical universe,
benchmark, outcome horizon, base currency, and rebalance cadence. All fields
must match the requested `CohortIdentity`; mixed populations are rejected rather
than silently pooled. The summary is deterministic and remains a derived
read-only product.
