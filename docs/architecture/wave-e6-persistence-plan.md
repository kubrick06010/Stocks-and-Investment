# Wave E6 persistence plan

No E6 tables are required. The source of truth is the existing immutable
research/report lineage. `NarrativeResult` is a derived, reproducible product
and is intentionally not persisted in V1. If a future system caches rendered
outputs, it must key them by report identity, renderer version and policy
version and remain disposable.
