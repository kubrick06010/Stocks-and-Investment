# ADR-004: Custom PIT shell with optional commodity adapters

- Status: accepted
- Date: 2026-08-19
- Decision owners: Program Lead / Chief Architect
- Supersedes: proposed custom-PIT-shell decision

## Context

Stocks-and-Investment needs two different capabilities:

1. a reproducible research system that selects securities using information
   available at a historical timestamp and preserves the complete decision;
2. commodity calculations for price-based experiments, portfolio statistics,
   and, eventually, execution validation.

The reviewed options do not provide those capabilities as one coherent
boundary. VectorBT provides vectorized portfolio/signal simulation and
parameter workflows; backtesting.py provides readable single-instrument
strategy backtests; QuantStats provides post-hoc performance statistics and
reports; QuantBT provides vectorized/event portfolio routes and walk-forward
optimization with a crypto/systematic-alpha emphasis; NautilusTrader provides
event-driven venue and execution simulation. None is the project’s authoritative
point-in-time filing, historical-universe, provenance, ResearchRun and
FactorScore store.

The validated C6 engine already provides the project-specific integrity model:
persisted ResearchRun selection, versioned universes and strategies,
point-in-time data access, explicit benchmark/cost/corporate-action semantics,
identity-safe portfolio simulation, and persisted BacktestRun lineage.

## Decision

The custom C6 engine owns orchestration and scientific integrity:

- historical information sets and public-availability barriers;
- versioned UniverseSnapshots and strategy identities;
- persisted ResearchRun/ResearchResult selection;
- portfolio formation, rebalancing, cash and transaction-cost semantics;
- corporate-action and price-adjustment policy;
- benchmark identity and return convention;
- BacktestRun/BacktestPeriod persistence and lineage;
- deterministic offline execution and validation.

Third-party libraries may be integrated only as optional, narrow adapters over
frozen project artifacts:

- **vectorbt**: price/technical vectorization and parameter exploration;
- **QuantStats**: descriptive analytics/report rendering from C5-produced,
  explicitly aligned return series;
- **NautilusTrader**, later: execution/fill/accounting validation for a frozen
  order stream, if a concrete fidelity requirement justifies the dependency.

`backtesting.py` and QuantBT are not adopted as core dependencies. They may be
used for isolated research/reference comparisons, but they must not become a
second source of portfolio, cost, or historical-selection truth.

## Required adapter contract

An adapter must accept a project-generated, immutable input manifest containing
at least:

- `ResearchRun`/`BacktestRun` identity;
- as-of and execution dates;
- ticker-keyed prices and observations;
- universe name/version and membership;
- benchmark and base currency;
- strategy/factor versions;
- transaction-cost model and rate;
- corporate-action and price-adjustment policy;
- return convention and data snapshot identity.

The adapter must not call a provider, query “latest” data, refresh a universe,
or infer missing values. It must return an auditable mapping from every
third-party result back to the input manifest. The project’s own calculations
remain authoritative when a third-party result differs.

## Consequences

Positive:

- Filing-date and survivorship correctness stay in one testable boundary.
- Historical decisions remain explainable after database close/reopen.
- Optional commodity tooling can be used without making it a runtime
  requirement or allowing provider-specific semantics into the domain.
- C5/C6 can cross-check external statistics while retaining independent tests.

Costs and limitations:

- The project must maintain adapters and contract fixtures.
- Large parameter sweeps and polished reports are less turnkey than in a
  specialized library.
- NautilusTrader would add substantial runtime and execution-model complexity.
- Optional dependencies require licensing and supply-chain review. In
  particular, the reviewed repositories identify vectorbt as Apache 2.0 with
  Commons Clause and backtesting.py as AGPL-3.0; these are not interchangeable
  distribution terms.

## Rejected alternatives

### Adopt vectorbt as the primary engine

Rejected because its flexible array/broadcasting and portfolio simulation do
not establish filing availability, historical universe membership, provenance,
or ResearchRun persistence. It remains the preferred optional accelerator for
price-only work after C6 has frozen the input. Signal timing and ticker/date
alignment must be tested explicitly.

### Adopt backtesting.py as the primary engine

Rejected because its documented `Backtest` model is centered on one OHLCV data
frame and a strategy class. That is a poor boundary for cross-sectional
fundamental screens and persisted historical research, and its AGPL-3.0
license requires deliberate product/legal review.

### Adopt QuantStats as the engine

Rejected because it is analytics/reporting, not portfolio simulation or data
governance. It can consume C5’s return series for optional presentation only.

### Adopt QuantBT as the primary engine

Rejected because it would introduce a second, evolving portfolio/accounting
surface oriented toward crypto and systematic alpha. Its walk-forward features
are useful references, but not a substitute for the project’s PIT contracts.

### Adopt NautilusTrader as the primary engine

Rejected for the current scope because its event-driven venue/execution model
solves a later fidelity problem and does not supply the project’s historical
fundamental information barrier. It remains a candidate for a separately
validated execution adapter.

## Verification sources

All sources were checked on **2026-08-19** and are official documentation,
official repositories, or official package metadata:

- [VectorBT docs](https://vectorbt.dev/) and [official repository](https://github.com/polakowo/vectorbt)
- [VectorBT portfolio API](https://github.com/polakowo/vectorbt/blob/master/vectorbt/portfolio/base.py)
- [backtesting.py repository](https://github.com/kernc/backtesting.py) and [official engine source](https://github.com/kernc/backtesting.py/blob/master/backtesting/backtesting.py)
- [backtesting.py license](https://github.com/kernc/backtesting.py/blob/master/LICENSE)
- [QuantStats repository](https://github.com/ranaroussi/quantstats) and [official reports source](https://github.com/ranaroussi/quantstats/blob/main/quantstats/reports.py)
- [QuantBT repository](https://github.com/BobbyAxerol/quantbt) and [package metadata](https://pypi.org/project/quantbt/)
- [NautilusTrader backtesting APIs](https://github.com/nautechsystems/nautilus_trader/blob/develop/docs/concepts/backtesting/apis-and-runs.md)
- [NautilusTrader quickstart](https://github.com/nautechsystems/nautilus_trader/blob/develop/docs/getting_started/quickstart.py)
