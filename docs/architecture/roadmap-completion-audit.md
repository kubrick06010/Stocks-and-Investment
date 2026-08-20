# Roadmap completion audit

Updated 2026-08-20. This document separates implementation evidence from
claims that require external historical data or a new product decision.

## Closed engineering scope

| Scope | Evidence | Status |
|---|---|---|
| Waves B–D | persisted PIT research, thesis, outcomes, backtests and reports | VALIDATED |
| E0 statistical contracts | typed cohorts and information barriers | VALIDATED |
| E1 statistical machinery | cohorts, IC, decay, uncertainty, multiple testing, OOS/walk-forward, interactions and turnover | VALIDATED |
| E1 artifact boundary | hash-pinned, license-identified, strict offline CSV/bundle normalization | VALIDATED |
| E1 real-data pilot | Kaggle v3 CC BY sample; 638 observations; deterministic SQLite rerun; explicit economic NO-GO | VALIDATED AS INTEGRATION PILOT |
| E2 filings | normalized filing evidence, claims, changes and PIT replay | VALIDATED |
| E3 automation | deterministic synchronous definitions, triggers, runs and replay | VALIDATED |
| E4 portfolio construction | deterministic long-only targets, constraints, cash and traded-notional costs | VALIDATED |
| E5 interactive research | local read-only provider-free interface and safe rendering | VALIDATED |
| E6 narrative boundary | deterministic structured renderer and explicitly disabled optional LLM slot | VALIDATED |

## Evidence still required for stronger scientific claims

The current tests use controlled fixtures. They prove identity, persistence,
determinism and leakage barriers; they do not prove that any factor or strategy
has economic edge in the real market.

The following remain a data-governance/product dependency, not an untested
implementation claim:

1. Delivery of an authorized, sufficiently large historical PIT panel with
   historical universe membership and economically defined delistings.
2. Confirmation that the full-panel license permits local retention and
   publication of derived aggregate research.
3. Re-running the E1 validation suite on that dataset, including non-overlapping
   cohorts, regime slices, uncertainty and out-of-sample evaluation.
4. Independent review of the resulting economic conclusions before presenting
   them as investment evidence.

The repository now has a deterministic ingestion boundary and a tracked
manifest for one real CC BY sample. Raw bytes are intentionally untracked. The
sample run is reproducible, but its 17 raw fundamental symbols are too few and
too selected for an economic claim. Full-panel access has been requested at
https://github.com/Finance-broski/pit-data-sample/issues/1.

The source decision and licensing boundary are recorded in
`docs/research/e1-authoritative-data-sources.md`.

Until those inputs exist, reports must state that synthetic and bounded
real-sample validation demonstrate machinery rather than profitability.

## Scope boundary

No implementation of a real LLM, dashboard, broker, live monitor or strategy
optimizer is implied by E6. Each requires a new architecture/security gate and
must consume the immutable artifacts already produced here.
