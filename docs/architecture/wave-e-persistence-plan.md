# Wave E.0 persistence plan

Wave E implementation should extend the existing SQLite facade additively. It
must not create one protocol per statistical table.

Durable V1 entities:

- dataset manifests and immutable source snapshot references;
- validation cohorts and exact FactorOutcomeObservation membership;
- statistical validation runs and methodology parameters;
- factor validation summaries needed to reproduce published conclusions.

Raw inputs remain the Wave D `factor_outcome_observations`. Bootstrap samples
and transient intermediate arrays need not be persisted; seeds, methods,
resample counts, block sizes, and final intervals must be recorded.

The implementation migration is expected to be additive schema v7, with tests
covering v6 → v7 preservation, idempotence, close/reopen, and deterministic
read-back. E0 introduces no migration yet.
