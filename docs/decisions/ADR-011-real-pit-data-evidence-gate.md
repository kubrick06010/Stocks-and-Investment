# ADR-011: Real PIT data evidence gate

## Status

Accepted, 2026-08-20.

## Context

Wave E's statistical machinery is validated on deterministic fixtures, but a
factor-profitability claim requires a large licensed panel with point-in-time
fundamentals, historical eligibility, inactive/delisted securities, corporate
actions and comparable outcomes. A public CC BY sample has real dates and
inactive names but only 99 price symbols and 17 fundamental symbols.

## Decision

1. Treat the Finance_Broski Kaggle v3 artifact as a **real-data integration
   pilot**, not economic evidence.
2. Pin archive/member hashes, source version, declared license and attribution
   in a tracked manifest; do not redistribute raw files from the repository.
3. Exclude unavailable outcomes and last-traded-price terminal-cash
   approximations from usable efficacy evidence.
4. Label the 99-security equal-weight return series a proxy, not an
   authoritative benchmark.
5. Request the full maintained panel and its legal/methodological evidence
   before re-running the economic gate.
6. If that request cannot meet the acceptance conditions, procure a
   CRSP/Compustat- or Sharadar-equivalent licensed snapshot after explicit
   approval of cost and terms.

## Consequences

The repository now proves real offline acquisition, normalization, PIT
filtering, statistical execution and persistence. It still makes no alpha or
profitability claim. Closing the external gate requires third-party delivery
or a user-approved commercial subscription; engineering tests cannot substitute
for that evidence.
