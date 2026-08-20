# ADR-003: Wave C research contracts and information barriers

Status: accepted

## Decision

Wave C consumes immutable, typed analytical records. `FactorObservation`
preserves value/status/units/period/as-of/calculation version and provenance;
`CriterionResult` preserves rule-level decisions; `FactorScore` preserves all
observations and rationale; `CompositeScore` preserves strategy identity,
weights, components, missing-data policy, and as-of date.

`UniverseSnapshot` is dated and versioned. `PointInTimeDataView` is the only
contract a backtest strategy may use for historical metrics/prices. It filters
canonical provenance availability at the simulation date. Future outcomes are
represented separately by `ResearchOutcome` and are not part of the research
information view.

Missing data is a strategy/scoring policy, not a global default. Supported
policies are `FAIL`, `IGNORE_AND_RENORMALIZE`, `PENALIZE`, and
`INSUFFICIENT_DATA`; the selected policy is persisted in `CompositeScore` and
later in the research run.

Portfolio accounting remains responsible for ledger truth. Portfolio analytics
receives state/cash-flow series and cannot mutate accounting records.
