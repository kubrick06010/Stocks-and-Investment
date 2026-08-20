# ADR-005: Statistical validation over immutable historical outcomes

## Status

Accepted for Wave E.0 contract freeze.

## Decision

Advanced validation consumes persisted `FactorOutcomeObservation` evidence and
an immutable, versioned dataset manifest. Statistical populations are defined
by explicit cohort and partition identities. Cross-sectional IC is calculated
per research date before longitudinal aggregation. Overlapping and
non-overlapping samples remain distinct.

Uncertainty methods, multiple-testing corrections, and walk-forward partitions
are explicit versioned methodology inputs. Validation produces evidence about
historical factors; it never changes factor weights, strategies, ResearchRuns,
or theses.

## Consequences

- Reproducible conclusions require manifests, exact cohort membership, and
  ValidationRun persistence.
- Pooled correlation alone is insufficient evidence.
- Moving-block bootstrap is available where temporal dependence matters.
- No statistical-significance claim is valid without sample, coverage,
  dependence, and multiple-testing metadata.
- E2–E6 remain downstream of a validated E1 foundation.
