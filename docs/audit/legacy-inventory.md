# Legacy inventory

## Scope

This audit covers the original Functions and Libs/, mainCode/, Test/, README, and both requirements files, plus the V2 package and tests that appeared during the shared-workspace audit. V2 files are recorded for handoff, not classified as legacy behavior. Evidence uses repository-relative paths and current line numbers.

## Components

| Component | Purpose | Evidence | State/disposition |
|---|---|---|---|
| mainCode/stock.py Fundamental_Analysis | Yahoo wrapper, FMP statements/ratios, valuations | mainCode/stock.py:105-155, 744-827 | Remote I/O, mutable state and formulas coupled; rewrite behind providers |
| mainCode/stock.py Technical_Analysis | Prices, SMA/EMA/MACD/RSI and charts | mainCode/stock.py:963-1115, 1117-1219 | Constructor performs I/O; indicators fragile/incomplete; rewrite as pure series |
| mainCode/stock.py stock | Multiple-inheritance façade | mainCode/stock.py:1568-1576 | Construction downloads prices and creates Yahoo client; replace with orchestration |
| mainCode/stock.py cryptocurrency | CryptoCompare minute history | mainCode/stock.py:1798-1849 | Remote-only and Python-2 arithmetic assumptions; isolate/defer |
| mainCode/stock.py universe helpers | NASDAQ FTP, other FTP, Wikipedia S&P 500 | mainCode/stock.py:1851-1905 | Current/unversioned membership; replace with versioned provider |
| mainCode/value_investment_lookup.py | Defensive screen and Sheets reporting | mainCode/value_investment_lookup.py:11-182, 215-344 | Missing sibling modules, identity comparisons, broad catches; preserve intent, rewrite |
| mainCode/Investment_value.py | Reconstruct invested value and plot ROI | mainCode/Investment_value.py:24-71, 73-145, 147-265 | Missing Gsheet, removed pandas APIs, fragile dates; replace with ledger |
| mainCode/Tradebill_Library.py | Momentum score and channel placeholder | mainCode/Tradebill_Library.py:10-85 | Syntax error; channelTrade only prints; deprecate/reimplement |
| mainCode/Algotrading.py | Ad hoc TSLA technical dump | mainCode/Algotrading.py:12-21 | Top-level network call/print; convert to command or remove |
| Functions and Libs/investing.py | Compounding and grid optimizer | Functions and Libs/investing.py:4-57, 59-74 | Python-2 print/xrange; formulas need characterization |
| Functions and Libs/email_msg.py | Gmail SMTP and credential parser | Functions and Libs/email_msg.py:9-33, 35-64 | Side effects and plaintext password example; remove from core |
| Test/ETF_data.py | ETF file and return plot | Test/ETF_data.py:1-8, 24-51 | Missing ticker_ETF.txt, Python-2 syntax, network, obsolete shape |
| Test/Test_EDGAR.py | EDGAR experiment | Test/Test_EDGAR.py:1-7 | Missing edgar package; no assertions |
| Test/Yahoo_datareader.py | FMP HTTP probe | Test/Yahoo_datareader.py:4-27 | Top-level live request without timeout/status/assertion |
| Test/expected_requirements.py | Optimizer plot | Test/expected_requirements.py:1-23 | Python-2 syntax and no assertions |
| Test/test_fundamentals.py | YahooFinancials KO smoke probe | Test/test_fundamentals.py:1-33 | Top-level live calls and prints; not a test |
| Test/Response_Yahoo.html | Captured Yahoo response | file present; no consumer found | Retain only if parser contract is restored |

## Newly present V2 baseline

pyproject.toml:1-35 defines Python >=3.12, pytest configuration and an empty runtime dependency set. src/stocks_investment/domain/models.py:16-125 provides immutable ticker, period, provenance, metric and score values. src/stocks_investment/interfaces/protocols.py:15-40 defines provider/storage seams. src/stocks_investment/cli/__init__.py:12-30 exposes version and doctor only. Tests cover these primitives and CLI output (tests/unit/test_cli.py:4-11; tests/unit/test_domain_models.py:18-42). This is a foundation, not migrated legacy behavior.

## Documentation drift

README instructs installation from nonexistent requiremnts.txt (README:9-15); actual files are requirements.txt and requirements_stock_class.txt. README claims phase 3 (README:17-20), while ROADMAP.md:1-24 describes a V2 forensic baseline.

## Conclusion

There is no coherent runnable legacy application entrypoint. Reusable intent exists in the stock data/indicator surface, defensive thresholds, transaction reconstruction concept, and compounding formulas; each requires offline characterization before migration.
