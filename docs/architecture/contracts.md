# V2 contracts

Protocols are intentionally narrow and provider-neutral:

- `MarketDataProvider`: fetch price bars, quotes, dividends, splits with retrieval and availability metadata.
- `FundamentalDataProvider`: fetch company identity, filings, statements, and share facts as of a requested date.
- `UniverseProvider`: return a versioned membership snapshot for a requested date.
- `StorageBackend`/`ResearchStorageBackend`: persist raw payloads, observations, research runs, theses, transactions, and migrations.
- `MetricCalculator`: calculate one or more named metrics from validated observations; never perform I/O.
- `TechnicalIndicatorProvider`: calculate indicators from price series.
- `ScreeningStrategy`/`ScoringStrategy`: accept snapshots and return explainable criteria/components.
- `BacktestEngine`: consume a strategy, versioned universe, PIT data, costs, benchmark, and date range.
- `PortfolioAnalyzer`: value a transaction ledger and calculate TWR, XIRR, and benchmark-relative metrics.
- `ThesisGenerator`: deterministic transformation of validated screen/score data into a thesis snapshot.

Contract rules: no provider-specific types in domain signatures; no naked float for a financial observation; no missing-to-zero coercion; no future observation in a historical run; every strategy has a stable version identifier.
