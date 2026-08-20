# ADR-004: Wave D research intelligence contracts

## Decision

Freeze immutable, source-referencing domain records for theses, changes,
comparisons, factor outcomes, watchlists and reports. Keep service interfaces
provider-independent and deterministic. Historical artifacts remain the source
of truth; future outcomes are post-hoc inputs only.

## Consequences

Wave D can compare and explain persisted research without regenerating it from
current data. Strategy comparison must expose incompatible assumptions. Factor
efficacy carries an explicit cohort: factor version, universe, benchmark,
horizon, base currency, and rebalance cadence are identity fields rather than
presentation metadata. Rendering and optional narrative layers remain outside
the domain.

The original D0 decision introduced no storage schema. Wave D closure later
implemented the frozen decision through additive SQLite schema v6.
