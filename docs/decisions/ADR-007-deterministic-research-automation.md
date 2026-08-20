# ADR-007: Deterministic research automation is a control plane

Status: Accepted for Wave E3 contract freeze.

## Decision

Automation coordinates the existing deterministic pipeline and persists typed
execution lineage. It does not own research calculations. Triggers carry a PIT
`as_of`, immutable source references and a deduplication key. Definitions,
pipeline versions, strategies and retries are explicit. Runs retain step-level
inputs, outputs and failures.

## Consequences

- scheduled and filing-driven work cannot create a hidden research engine;
- duplicate/replayed triggers are observable and idempotent;
- partial failure, retry and rate-limit behavior is auditable;
- historical automation is reproducible without provider access after its
  artifacts are persisted;
- V1 deliberately excludes daemons, distributed queues and notifications.
