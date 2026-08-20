# Backtesting engine research

Status: refreshed 2026-08-19

This review uses primary sources only: each project's official documentation,
official source repository, or official package metadata. It evaluates the
engines as components of Stocks-and-Investment, not as replacements for the
validated C6 research and persistence model.

## Executive recommendation

Retain the in-repository C6 engine as the system of record for historical
cross-sectional research. It is the only evaluated option whose contract is
already aligned with this project’s requirements for persisted `ResearchRun`
lineage, point-in-time filing availability, versioned universe snapshots,
explicit information barriers, turnover-based costs, corporate-action policy,
and deterministic SQLite read-back.

Use third-party libraries only behind narrow, optional adapters:

1. **vectorbt** for vectorized price/indicator experiments and parameter-grid
   exploration after C6 has produced a validated, identity-safe market-data
   view. Its own documentation warns that signals generated from a price must
   be shifted when execution is intended on a later tick.
2. **QuantStats** for descriptive portfolio analytics and optional report
   rendering after C6/C5 have supplied an already aligned return series. It
   must not fetch data, define the benchmark, or become the calculation source
   of truth.

Do not integrate `backtesting.py`, QuantBT, or NautilusTrader into the core
research path at this stage. They solve different problems or introduce
unnecessary operational/licensing scope for the current product. They remain
useful references or optional future sandboxes, with the limitations below.

## Capability comparison

| Option | Cross-sectional PIT fundamentals | Rebalancing / multi-asset | Costs and execution | Technical strategies / sweeps | Walk-forward / OOS | Benchmark/reporting | Decision |
|---|---|---|---|---|---|---|---|
| **C6 custom engine** | Native project contract: persisted runs, availability dates, universe versions, provenance and leakage tests | Native historical ResearchRun → portfolio rebalance path; identity keyed by ticker | Native turnover notional, explicit costs, cash and corporate-action policy | C6 owns research semantics; technical calculations remain independent and deterministic | PIT views and historical runs are authoritative; Wave E supplies statistical walk-forward | C5 analytics and persisted BacktestRun/period lineage | **System of record** |
| **vectorbt** | No domain-level filing/PIT or survivorship model; caller must prepare safe arrays | Strong vectorized portfolio simulation, broadcasting and grouping; caller owns cross-sectional semantics | Fees, fixed fees and slippage are supported; semantics must be mapped and tested | Excellent fit for vectorized indicators, signals and parameter products | Official resources include walk-forward validation examples; caller must enforce research/OOS boundaries | Portfolio statistics and plots; caller owns canonical benchmark and provenance | **Optional adapter** |
| **backtesting.py** | Single `DataFrame` input and strategy callbacks do not provide filing availability or versioned universes | Primarily one OHLCV instrument per `Backtest`; not the natural cross-sectional screen/rebalance boundary | Spread, commission and callable commission supported; documented commission is applied at entry and exit | Clear single-instrument technical experiments and optimizer | Official examples show ML walk-forward usage; no project-level PIT cohort contract | Detailed trade statistics and plots; not the project persistence model | **Do not integrate core** |
| **QuantStats** | None; consumes returns | None; analytics only | Does not model fills, turnover or costs; those must already be in returns | None; no strategy simulation | None; post-hoc analytics only | Strong stats, plots and HTML tear sheets, including benchmark inputs | **Optional report adapter** |
| **QuantBT** | No project PIT/provenance/universe contract; official project is oriented toward crypto/systematic-alpha workflows | Multi-symbol native portfolio and event routes; requires a separate data/accounting mapping | Explicit fee/slippage/leverage routes; semantics differ from C6 and require reconciliation | Vectorized/Numba/event routes and walk-forward optimization | Train/test and walk-forward endpoints are advertised; optimization scope is broader than this gate | Metrics/plots and optional QuantStats/Nautilus integrations | **Do not integrate core** |
| **NautilusTrader** | Catalog and replay infrastructure do not establish public filing availability or our universe snapshots | Strong event-driven venue/instrument/order model and multi-data replay | Detailed simulated exchange, execution and account reports; high fidelity but larger operational scope | Strong bar/tick/order-book strategy and execution workflows | Repeated/configured backtests are supported; OOS/PIT research cohorts remain caller-owned | Account, positions and fills reports; not the canonical ResearchRun/FactorScore store | **Future execution-validation adapter only** |

## Detailed findings

### vectorbt

The official repository describes `Portfolio.from_orders`, `from_signals`, and
`from_order_func` as portfolio simulation modes. The portfolio accepts array
inputs for price, fees, fixed fees, slippage, sizing, cash sharing and related
execution controls. Broadcasting and grouping support multi-asset experiments.
The official resources also include parameter grids and walk-forward validation
examples.

This is a good commodity accelerator for pure price/technical research once
C6 has materialized an approved input view. It is not a provider, filing
database, universe service, or provenance layer. Its flexible broadcasting can
also make accidental positional alignment easy, so the adapter must require
ticker/date keyed inputs and retain an audit mapping. A signal generated from
the same close must be shifted before execution where the methodology requires
next-bar execution; this is an explicit upstream warning in the official
portfolio documentation.

Licensing is a deployment consideration: the official repository identifies an
Apache 2.0 license with Commons Clause. Legal review is required before making
it a mandatory runtime dependency or redistributing it in a packaged product.

Official sources checked:

- [VectorBT documentation](https://vectorbt.dev/)
- [Portfolio API source and execution parameters](https://github.com/polakowo/vectorbt/blob/master/vectorbt/portfolio/base.py)
- [Official resources, including parameter grids and walk-forward validation](https://github.com/polakowo/vectorbt/blob/master/docs/docs/getting-started/resources.md)
- [Official source repository and license](https://github.com/polakowo/vectorbt)

### backtesting.py

The official API takes a single OHLCV `DataFrame` and a `Strategy` subclass.
It offers readable strategy callbacks, detailed trade statistics, commission,
spread and an optimizer. The documented commission behavior applies commission
at trade entry and exit; a callable can represent more complex commission
rules.

It is useful for isolated, readable single-instrument technical experiments.
Its input and strategy model do not provide the project’s public-availability
semantics, historical universe membership, cross-sectional selection, or
ResearchRun persistence. Adapting it for those purposes would duplicate the
core C6 orchestration and make it harder to prove the information barrier.
The official repository is AGPL-3.0, an additional distribution constraint.

Official sources checked:

- [Official repository and feature overview](https://github.com/kernc/backtesting.py)
- [Official Backtest constructor and commission semantics](https://github.com/kernc/backtesting.py/blob/master/backtesting/backtesting.py)
- [Official machine-learning walk-forward example](https://kernc.github.io/backtesting.py/doc/examples/Trading%20with%20Machine%20Learning.html)
- [Official license](https://github.com/kernc/backtesting.py/blob/master/LICENSE)

### QuantStats

QuantStats is an analytics and reporting library, not a simulator. Its
official repository exposes statistics such as CAGR, Sharpe, Calmar,
drawdown and volatility, plots, and HTML tear sheets with optional benchmark
returns. It expects a prepared return series and therefore cannot enforce
fills, turnover, corporate actions, PIT inputs or benchmark identity.

Use it only after C5 has calculated and aligned the canonical return series.
The adapter must pass explicit series and benchmark data rather than ticker
symbols, because provider fetching would violate offline and historical
reproducibility. Keep C5’s independently tested values authoritative and
treat QuantStats output as presentation or cross-check. The official
repository reports release `v0.0.81` dated 2026-01-13 and Apache-2.0 licensing;
dependency versions still require supply-chain review.

Official sources checked:

- [Official repository and capabilities](https://github.com/ranaroussi/quantstats)
- [Official reports implementation](https://github.com/ranaroussi/quantstats/blob/main/quantstats/reports.py)
- [Official plotting/benchmark implementation](https://github.com/ranaroussi/quantstats/blob/main/quantstats/_plotting/wrappers.py)
- [Official license](https://github.com/ranaroussi/quantstats/blob/main/LICENSE.txt)

### QuantBT

The evaluated project is [BobbyAxerol/quantbt](https://github.com/BobbyAxerol/quantbt),
the official repository behind the `quantbt` package. Its README describes
vectorized, Numba-accelerated, event-driven and explicit-order routes, native
multi-symbol portfolios, fees/slippage, and train/test or walk-forward
optimization. It also documents optional QuantStats and NautilusTrader
validation.

Those capabilities are relevant to future execution research, but the project
is explicitly positioned around crypto and systematic-alpha workflows. Its
contracts do not replace our persisted PIT fundamental view, historical
universe snapshots, FactorScore provenance, or ResearchRun lineage. Adding it
now would create a second accounting/simulation semantics surface. Keep it as
a research reference or isolated benchmark until a concrete use case and
reconciliation test justify an adapter. Review the exact commit and license
again before any future adoption.

Official sources checked:

- [Official QuantBT repository and README](https://github.com/BobbyAxerol/quantbt)
- [Official support guidance](https://github.com/BobbyAxerol/quantbt/blob/main/SUPPORT.md)
- [Official package metadata](https://pypi.org/project/quantbt/)

### NautilusTrader

NautilusTrader provides a serious event-driven execution model. Official docs
describe a low-level `BacktestEngine` and a high-level `BacktestNode` backed by
a `ParquetDataCatalog`, chronological replay, simulated venues, instruments,
strategies and execution algorithms. It produces account, positions and order
fills reports and supports detailed trade/execution semantics.

This is valuable when validating execution, market microstructure, order-book
or venue behavior. It is not a replacement for the project’s research layer:
the catalog does not make SEC filing availability, point-in-time universes,
factor versioning or ResearchRun persistence true by itself. It also brings a
larger Rust/Python/runtime model and a live-trading-oriented architecture. A
future adapter should translate a frozen C6 portfolio/order stream into a
Nautilus validation run and compare fills/accounting; it must not let
Nautilus select securities or query latest fundamentals.

Official sources checked:

- [Official backtesting APIs](https://github.com/nautechsystems/nautilus_trader/blob/develop/docs/concepts/backtesting/apis-and-runs.md)
- [Official quickstart and reports](https://github.com/nautechsystems/nautilus_trader/blob/develop/docs/getting_started/quickstart.py)
- [Official high-level catalog workflow](https://github.com/nautechsystems/nautilus_trader/blob/develop/docs/getting_started/backtest_high_level.py)
- [Official execution flow](https://github.com/nautechsystems/nautilus_trader/blob/develop/docs/concepts/backtesting/execution-flow.md)
- [Official repository](https://github.com/nautechsystems/nautilus_trader)

### Custom validated C6 engine

C6 is not a generic framework in the same category as the options above. It is
the project’s domain-specific integrity boundary. It consumes persisted
historical ResearchRuns rather than silently recalculating a strategy; keeps
security identity through selection and price alignment; records universe,
strategy, benchmark, costs and corporate-action policies; and persists
BacktestRun/BacktestPeriod lineage for close/reopen inspection.

This is the correct owner of cross-sectional PIT fundamental screens and
historical portfolio formation. Its limitation is commodity functionality:
technical signal grids, large parameter sweeps, venue-level order simulation
and polished tear sheets need more in-house work or optional adapters. That is
an acceptable boundary because those conveniences must not weaken historical
truth.

## Capability decisions

### Cross-sectional PIT fundamental screens

Use C6 plus the existing PIT data view, persisted ResearchRuns and versioned
UniverseSnapshots. None of the third-party candidates can be the authority for
filing-date availability or survivorship metadata. An adapter may export a
frozen, date-keyed dataset to a library, but the export must retain snapshot
identity and the run must remain linked to C6 lineage.

### Rebalancing and portfolio construction

Use C6 for top-N selection, equal-weight formation, rebalances, holdings,
cash, turnover and transaction costs. vectorbt can be used for a separately
validated price-only experiment, but its output cannot replace persisted
BacktestRun. backtesting.py is not suitable as the cross-sectional coordinator.

### Transaction costs and execution

C6 owns the economic definition: costs on explicit traded notional, with
turnover and gross/net returns recorded separately. Third-party fee/slippage
parameters can be used only after a contract test maps them to this definition.
NautilusTrader is the strongest future candidate for execution validation, not
for the selection decision. backtesting.py’s entry/exit convention and
QuantBT’s fee/leverage conventions must not be silently equated with C6.

### Technical strategies and parameter sweeps

Keep indicator calculations in the project’s technical layer. For broad,
vectorized price-only grids, an optional vectorbt adapter is the preferred
commodity path, subject to licensing review and shifted-signal tests. Do not
use parameter optimization to tune fundamentals on the full history. Wave E’s
walk-forward contracts remain the authority for train, validation and OOS.

### Walk-forward and out-of-sample validation

The project’s Wave E contracts define the information and partition boundary.
Third-party examples can accelerate calculations, but they cannot choose
windows or leak observations. Pass explicit train/validation/OOS arrays
generated by the project and persist project window IDs and data manifests.
QuantBT and vectorbt offer useful workflow references; neither is accepted as
the PIT governance layer.

### Benchmarking and reporting

C5/C6 calculate canonical benchmark-relative metrics with identity-safe date
alignment. QuantStats is the preferred optional reporting adapter because it
consumes prepared return series and can render standard statistics/tear sheets.
Its output is non-authoritative and must preserve the project’s
research-versus-outcome boundary. Do not pass provider ticker names that cause
implicit downloads.

## Integration boundary and non-goals

Any future adapter must satisfy these rules:

- Input is a frozen, persisted, PIT-approved view with explicit dates, tickers,
  benchmark and currency.
- No provider call, latest-data lookup, or current-universe substitution is
  allowed inside the adapter.
- Every output retains upstream `ResearchRun` or `BacktestRun` identity.
- Costs, corporate actions, adjustment policy and return convention are named,
  not inferred from a library default.
- Numerical cross-checks use synthetic fixtures and independently derived
  expected values.
- The custom engine remains executable without optional third-party packages.

Explicitly do not use during the current roadmap stage:

- backtesting.py as the cross-sectional PIT or portfolio engine;
- QuantBT as a second portfolio/accounting authority;
- NautilusTrader as the research selector or fundamental-data orchestrator;
- QuantStats as a calculation source of truth;
- vectorbt as a substitute for universe, filing, provenance or outcome
  persistence;
- any optimizer to select strategy weights or thresholds on the full history.

## Research limitations

This is an architectural fit assessment, not a runtime benchmark. Official
docs describe capabilities but do not prove that each library handles this
project’s accounting conventions or security identity without adapter tests.
Version, license and API behavior can change; repeat this review before adding
an optional dependency. No library removes the need for survivorship-bias
analysis, non-overlapping cohorts, walk-forward tests, transaction-cost
sensitivity, and independent golden calculations.

Date checked: **2026-08-19**.
