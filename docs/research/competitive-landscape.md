# Competitive landscape

Comparative research for the Investment Research & Decision Engine. Checked **2026-08-19**. Sources are the projects' official GitHub repositories, repository documentation, release pages, and license files. “Activity” is limited to what those official pages expose; absence of a visible release or recent commit is reported as uncertainty, not as proof of abandonment.

## Executive conclusion

No reference project supplies the complete target system. OpenBB and finagg are strongest as data-access and normalization references; crible and the two screeners are useful for local screening ergonomics and persistence patterns; vectorbt and QuantStats cover commodity quantitative experimentation and reporting; NautilusTrader demonstrates a serious event-driven execution architecture. Stocks-and-Investment should borrow narrowly defined concepts while retaining ownership of its domain models, provenance, point-in-time rules, validated formulas, historical research runs, thesis lineage, and scientific-integrity controls.

The project will **not** become a wrapper around any one of these systems. Third-party dependencies remain optional and must sit behind provider, analytics, or adapter boundaries.

## Comparison matrix

| Project | What it solves better | Concepts to reuse | Potentially useful dependency | Architectural risks to avoid | Explicitly out of scope | Official status checked |
|---|---|---|---|---|---|---|
| [OpenBB](https://github.com/OpenBB-finance/OpenBB) | Broad analyst-facing financial data platform, provider extensions, API/Workspace integration, and a large research surface. | Capability-based provider extensions, normalized endpoint models, CLI/API separation, provider configuration, and research UX. | Optional provider-adapter inspiration; direct dependency only after license and provenance review. | Provider breadth is not data authority; latest-data APIs do not automatically provide PIT history; large framework surface can dominate the domain. AGPLv3 requires legal review before linking/distributing. | OpenBB Workspace/Desktop, AI-agent integration, broad provider marketplace, and wholesale platform adoption. | Active releases and recent maintenance visible. License: [AGPLv3](https://github.com/OpenBB-finance/OpenBB/blob/develop/LICENSE). |
| [crible](https://github.com/maxgfr/crible) | Self-hosted fundamental screener with local data, DSL, CLI/API/MCP surfaces, refresh health, and persisted screening. | Local-first mirrors, last-good data, field catalogues, source audits, and screen-history ergonomics. | Patterns may be reused; DuckDB/Parquet are future candidates only if scale demands them. | Unofficial Yahoo data may be rate-limited or contractually uncertain; last-good data can be stale; current freshness is not filing availability or a historical universe. | Hosted screener, MCP agent surface, broad nightly crawl, and treating a current mirror as a historical universe. | MIT license, current changelog, and active data-source audit visible. Several source terms are explicitly uncertain. [License](https://github.com/maxgfr/crible/blob/main/LICENSE). |
| [finagg](https://github.com/theOGognf/finagg) | Aggregation and normalization of historical data from free APIs into local SQL datasets, with HTTP caching and SQLAlchemy. | API-to-dataset separation, cache/database configuration, source modules, and normalization pipelines. | Optional ingestion experiment after licensing, PIT, and schema review. SQLAlchemy/requests-cache are references, not mandatory dependencies. | API “history” can still be restated/latest; API keys and user agents matter; sparse series may be skipped; relational normalization alone is not provenance. | API-key-driven dataset installer, broad macro scope, and canonical fundamentals storage. | README reports Python 3.10+, Apache-2.0, SQLite/SQLAlchemy/cache. Current release cadence is uncertain. [License](https://github.com/theOGognf/finagg/blob/main/LICENSE). |
| [vectorbt](https://github.com/polakowo/vectorbt) | High-throughput vectorized experimentation, Numba/Rust acceleration, parameter sweeps, portfolio records, and interactive exploration. | Indexed arrays, records for orders/trades/positions/drawdowns, and separation of exploratory research from analysis. | Optional acceleration/exploration only; not the PIT source of truth. | Vectorization makes positional misalignment easy; sweeps encourage overfitting; market-data helpers do not establish availability; community license is Apache-2.0 with Commons Clause. | Replacing C6, PIT fundamentals, universe reconstruction, or scientific validation with grid search. | Official docs show current 2026 maintenance and fair-code terms. [License](https://github.com/polakowo/vectorbt/blob/master/LICENSE.md). |
| [QuantStats](https://github.com/ranaroussi/quantstats) | Portfolio profiling, risk/performance statistics, plots, HTML tear sheets, and Monte Carlo helpers. | Presentation/report separation, return-series inputs, metric vocabulary, and benchmark-aware reporting. | Optional renderer after our canonical analytics produce series. | Reports can hide frequency, annualization, risk-free, benchmark, and missing-date assumptions; it is not a ledger or PIT engine. | Accounting authority, canonical evidence, or unrecorded metric assumptions. | Official repository reports Apache-2.0 and release `v0.0.81` on 2026-01-13. [License](https://github.com/ranaroussi/quantstats/blob/main/LICENSE.txt). |
| [NautilusTrader](https://github.com/nautechsystems/nautilus_trader) | Rust-native deterministic event-driven trading/backtesting, unified domain model, adapters, precise money/quantity handling, and release/security controls. | Typed financial state, event transitions, deterministic replay, exact arithmetic, and adapter boundaries. | Future execution/backtest research only; adoption is a major decision. | It executes live capital; Rust/PyO3 and event-driven complexity exceed the current research core; LGPLv3/trademark obligations require review. | Live trading, broker/venue connectivity, HFT infrastructure, and the full Rust runtime. | Official releases show active development, including `1.227.0 Beta` (2026-05-18); docs state LGPL-3.0-or-later and trademark rules. [License](https://github.com/nautechsystems/nautilus_trader/blob/develop/LICENSE). |
| [KarneeshkarV/screener](https://github.com/KarneeshkarV/screener) | Broad Python CLI workflows across US/Indian equities: composable screens, persisted history, PIT-aware cards, replay, factor tearsheets, and walk-forward commands. | CLI grouping, persisted screen snapshots, replay lineage, `--as-of`, structured output, and separation of exploratory sweeps from fuller backtests. | Reference implementation and test ideas; not a dependency. | Provider-specific workflows, optional keys, current/unofficial data, broad feature surface, and optimization/conviction composites can encourage data mining. | Indian/provider breadth, live options/promoter workflows, optimization, and trading-oriented conviction orchestration. | Official page shows 134 commits and CI/tests, but no visible releases; license is not clearly exposed, so adoption licensing is **uncertain**. |
| [EdwinForss/Stock_Screener](https://github.com/EdwinForss/Stock_Screener) | Small value screener with grouped metrics, Graham/Buffett filters, Excel export, and SQLite output. | Lightweight CLI, durable SQLite export, metric grouping, and filter presets. | No production dependency; inspiration/fixture reference only. | Five-commit project, yfinance/latest-data coupling, unvalidated “80+ metrics,” and nonstandard personal/educational license wording. | Wholesale formula port, export-as-provenance, or provider/strategy runtime. | Official README shows five commits and personal/educational terms; no standard license file was visible, so maintenance and redistribution rights are uncertain. |

## Project-specific findings

### OpenBB

OpenBB is the strongest reference for extensible provider capability and analyst-facing composition. Its provider abstraction is useful only after our canonical observation and provenance contracts are applied at the adapter boundary. Its own disclaimer says data is not necessarily accurate, reinforcing that provider integration cannot substitute for validation, PIT availability, or source lineage. The AGPLv3 license is a material adoption constraint.

### crible and finagg

Together these projects show two valuable patterns: a local-first screener with explicit source audits, and an API-to-dataset ingestion pipeline with cache/database controls. We should reuse the audit discipline, freshness/coverage reporting, and snapshot concepts. We must keep our own filing-date, restatement, universe-snapshot, and availability semantics; a current local mirror is not automatically a historical information set.

### vectorbt, QuantStats, and NautilusTrader

vectorbt is suitable for exploratory matrix workloads; QuantStats is suitable for optional presentation; NautilusTrader is a reference for high-integrity event processing and exact financial types. None should replace our validated persistence, accounting, PIT view, or backtest contracts. NautilusTrader in particular solves live/execution infrastructure, not the current research-laboratory problem.

### The two screeners

KarneeshkarV/screener is useful for CLI surfaces, replay lineage, factor tearsheets, and explicit caveats around stale data and exploratory sweeps. EdwinForss/Stock_Screener is useful historical evidence for the original project’s desired user experience: grouped metrics, presets, and durable exports. Neither should be treated as a formula, provenance, or licensing baseline.

## Recommended use in Stocks-and-Investment

| Need | Preferred references | Boundary in this project |
|---|---|---|
| Provider capability design | OpenBB, finagg | Adapters emit canonical observations with availability and provenance; provider types do not leak into domain logic. |
| Local ingestion/cache | crible, finagg | Cache is versioned operational state; PIT access remains enforced by our data-view/storage layer. |
| Exploratory research | vectorbt | Optional sandbox; persisted validated backtests remain authoritative. |
| Performance presentation | QuantStats | Optional renderer over canonical analytics with recorded assumptions. |
| Event-driven/execution research | NautilusTrader | Study only until execution scope is explicitly approved. |
| CLI/screen ergonomics | crible, KarneeshkarV/screener, EdwinForss/Stock_Screener | Borrow usability patterns without importing provider or strategy assumptions. |

## Explicit non-goals

V2 is not a broker/execution system, live-trading engine, prediction oracle, opaque LLM recommender, high-frequency platform, options platform, or wrapper around one third-party project. It will borrow commodity primitives while owning domain models, provenance, formula validation, PIT access, research-run persistence, thesis explainability, statistical validation, and bias controls.

## Source register

All links are official project repositories or first-party repository documents, checked 2026-08-19:

- [OpenBB repository](https://github.com/OpenBB-finance/OpenBB), [releases](https://github.com/OpenBB-finance/OpenBB/releases), [license](https://github.com/OpenBB-finance/OpenBB/blob/develop/LICENSE)
- [crible repository](https://github.com/maxgfr/crible), [data-source audit](https://github.com/maxgfr/crible/blob/main/docs/DATA-SOURCES.md), [changelog](https://github.com/maxgfr/crible/blob/main/docs/CHANGELOG.md), [license](https://github.com/maxgfr/crible/blob/main/LICENSE)
- [finagg repository](https://github.com/theOGognf/finagg), [license](https://github.com/theOGognf/finagg/blob/main/LICENSE)
- [vectorbt repository](https://github.com/polakowo/vectorbt), [documentation](https://vectorbt.dev/), [license](https://github.com/polakowo/vectorbt/blob/master/LICENSE.md)
- [QuantStats repository](https://github.com/ranaroussi/quantstats), [releases](https://github.com/ranaroussi/quantstats/releases), [license](https://github.com/ranaroussi/quantstats/blob/main/LICENSE.txt)
- [NautilusTrader repository](https://github.com/nautechsystems/nautilus_trader), [docs](https://github.com/nautechsystems/nautilus_trader/tree/develop/docs), [releases](https://github.com/nautechsystems/nautilus_trader/releases), [license](https://github.com/nautechsystems/nautilus_trader/blob/develop/LICENSE)
- [KarneeshkarV/screener repository](https://github.com/KarneeshkarV/screener), [README](https://github.com/KarneeshkarV/screener/blob/main/README.md)
- [EdwinForss/Stock_Screener repository](https://github.com/EdwinForss/Stock_Screener), [README](https://github.com/EdwinForss/Stock_Screener/blob/main/README.md)

## Limitations and follow-up

- GitHub metadata can lag the latest commit or omit license information; uncertain items are marked rather than inferred.
- Provider terms, rate limits, coverage, and licensing change independently of these repositories and require a fresh review before adoption.
- Stars, watchers, and commit counts indicate public activity, not correctness, support, or security.
- No comparison above validates historical universes, as-filed restatements, or absence of look-ahead bias for our use case. Those remain release-blocking responsibilities of this project.
