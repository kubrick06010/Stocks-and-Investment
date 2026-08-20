# V2 readiness report

## Executive finding

The repository contains useful investment intent but is not an executable, reproducible platform. It is a set of Python 2-era scripts centered on a 2,068-line multiple-inheritance `stock` class, remote Yahoo/Financial Modeling Prep calls, and Google Sheets portfolio input. The clean migration boundary is a strangler architecture: preserve the legacy tree for characterization, build a typed provider-neutral package, then retire legacy modules after golden coverage.

The first V2 vertical slice now proves an offline `Ticker -> FixtureProvider -> provenance-aware observation -> SQLite -> ResearchRun/ResearchResult -> reopen/read-back` path. The legacy tree remains intentionally outside the V2 compile/test gate; its four known AST failures remain documented below.

## Evidence

- `mainCode/stock.py` combines HTTP acquisition, normalized/unnormalized statement parsing, fundamentals, indicators, plotting, ticker-universe downloads, and crypto handling.
- `mainCode/Investment_value.py:140` constructs removed `pandas.Panel`; `:129` and `:167` use removed `DataFrame.append`.
- `mainCode/value_investment_lookup.py:1-8` depends on `sys.path` mutation, an implicit sibling repository, and an unavailable `google_sheet_class`.
- `mainCode/Investment_value.py:20` contains a hard-coded Google spreadsheet ID.
- `mainCode/stock.py:951` uses `is` for string comparison and `:1657`, `:1674`, `:1688` use removed append APIs.
- `mainCode/Tradebill_Library.py:10` has invalid Python syntax in `signal_IS=9`.
- Formula review finds several materially wrong or ambiguous calculations: book value uses current assets less intangibles less current liabilities; BVPS divides by market cap; TTM EPS sums only three quarters; Graham number can take the square root of negative/non-meaningful values; the defensive screen labels `min_price_earnings` but requires PE below it.

## Release blockers

1. No canonical time, period, currency, unit, filing/publication-date, or provenance model.
2. No historical snapshot persistence; current remote data can leak future revisions into historical research.
3. No provider-independent interfaces or cache.
4. No verified formula specification or golden fixtures.
5. Portfolio results are value-minus-principal plots, not TWR/XIRR accounting.
6. Legacy runtime has syntax errors, removed pandas APIs, stale dependencies, and hidden external imports.

## Recommended architecture checkpoint

Use typed immutable domain observations with explicit `effective_date`, `available_at`, `period_start`, `period_end`, `currency`, `units`, and `DataProvenance`. Keep providers in `data/`, calculations in `fundamentals/` and `technical/`, decisions in strategies/scoring/thesis, and persistence in storage. Every research run stores strategy version, universe version, parameters, data snapshot, and git revision. A backtest must reject an observation whose `available_at` is after the simulation date.
