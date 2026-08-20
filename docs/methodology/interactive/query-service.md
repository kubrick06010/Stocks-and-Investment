# Interactive research query service

`DeterministicInteractiveResearchService` is a provider-free, read-only
application adapter over the persisted SQLite evidence store.

It accepts a frozen `ResearchViewRequest` and returns a `ResearchView`. Every
view is assembled from persisted Wave B–E artifacts and existing report,
comparison, and factor-efficacy builders. The service never calls providers,
downloads current data, recomputes a historical strategy, or uses the clock.

Historical filtering uses the request's explicit `as_of` date. Outcomes are
excluded by default. `OutcomeVisibility.SEPARATE` may expose persisted outcome
records only in a post-hoc section; it cannot alter research sections.

The service preserves ticker, run, strategy/factor version, horizon, cohort,
and source-reference identity. Results are sorted by persisted order and then
limited deterministically. Duplicate source references are removed by their
`(entity_type, entity_id, field)` identity.

Missing records return `NOT_FOUND`. Missing dependencies of an existing
artifact return `INSUFFICIENT_DATA`; incompatible strategy or factor cohorts
return `INCOMPATIBLE`. These states are explicit and are never represented by
fabricated zero values.

The service is intentionally not an export surface. The package/CLI integrator
owns exports and presentation wiring.
