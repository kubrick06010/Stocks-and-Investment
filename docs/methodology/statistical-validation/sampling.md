# E1B — Cohort sampling

This module constructs deterministic validation cohorts from persisted
`FactorOutcomeObservation` records. It does not fetch providers, recompute
factor scores, or mutate stored research artifacts.

## Identity and eligibility

An observation is eligible only when all frozen `CohortIdentity` fields match:

- factor version;
- historical universe;
- as-of date window;
- outcome horizon;
- rebalance cadence;
- base currency;
- benchmark.

Eligible means that the observation belongs to the requested population. It
does not imply that its outcome is usable. A usable observation also requires a
factor score, security return, benchmark return, excess return, and a status of
`valid`, `usable`, or `complete`. Missing outcomes are excluded and counted;
they are never converted to zero.

Coverage is selected usable observations divided by eligible observations.
The result reports `INSUFFICIENT_SAMPLE`, `INSUFFICIENT_COVERAGE`,
`INCOMPATIBLE_COHORT`, or `VALID` explicitly.

## Sampling methods

`OVERLAPPING` selects every usable eligible observation in deterministic order
(`as_of`, ticker, research-run identity). Its limitations explicitly state
that forward windows may overlap and therefore are not independent.

`NON_OVERLAPPING` applies the forward-window rule independently per ticker. A
window is the half-open interval `[as_of, as_of + horizon)`. Observations are
sorted by date and run identity; the earliest eligible window is selected, and
the next selected window must start on or after the previous window's end.
Different tickers may have windows covering the same dates because the policy
removes repeated exposure for a security, not cross-sectional observations.

Horizons use explicit `D`, `M`, or `Y` units, for example `90D`, `3M`, and
`1Y`. Month and year arithmetic clamps month-end dates to the last valid day
of the target month. Unsupported values fail loudly.

## Contract gap

The frozen `FactorOutcomeObservation` contract has no numeric observation ID.
The sampler therefore derives a deterministic local ID from factor identity,
research run, ticker, and as-of date. A future additive contract may provide a
persisted observation identifier; until then this local identity prevents
separate factor observations from colliding.

The frozen `ValidationCohort` contract stores selected IDs and policy fields,
while this module's `CohortSamplingResult` carries eligibility, exclusions,
coverage, status, and limitations. No shared contract was modified for E1B.
