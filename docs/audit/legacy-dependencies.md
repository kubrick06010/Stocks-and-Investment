# Legacy dependency and coupling inventory

## Declared and observed dependencies

requirements.txt:1-51 pins pandas 0.24.2, numpy 1.16.3, pandas-datareader 0.7.0, matplotlib 3.0.3, requests 2.21.0, lxml 4.3.3, yahoofinancials 1.5 and TensorFlow/Keras 1.13/1.15, plus Google auth/client, PyPDF2, scipy and seaborn without direct import evidence. requirements_stock_class.txt:1-21 overlaps the same obsolete stack. Observed imports include requests, numpy, pandas, pandas_datareader, matplotlib/pylab, lxml, yahoofinancials, ftplib, decimal, email and smtplib (mainCode/stock.py:71-98; Functions and Libs/email_msg.py:1-5; Functions and Libs/investing.py:2). edgar is imported but undeclared (Test/Test_EDGAR.py:1); google_sheet_class is imported but absent (mainCode/Investment_value.py:6-7; mainCode/value_investment_lookup.py:5-8).

## External systems

| System | Evidence | Coupling/failure mode |
|---|---|---|
| Yahoo prices/DataReader | mainCode/stock.py:1587, 1653 | Old provider name/schema required in constructor |
| YahooFinancials | mainCode/stock.py:87, 110, 482-493 | Live wrapper keys/current values |
| Financial Modeling Prep | mainCode/stock.py:747-827, 612-624 | URLs/keys embedded; no timeout/status/auth/retry/cache/provenance |
| Google Finance | mainCode/stock.py:1705-1744 | Obsolete endpoint/parser |
| CryptoCompare | mainCode/stock.py:1802-1849 | Live pagination and Python-2 arithmetic |
| NASDAQ FTP | mainCode/stock.py:1851-1900 | Current universe, no effective date/version |
| Wikipedia | mainCode/stock.py:1902-1905 | Current S&P membership/survivorship bias |
| Google Sheets/sibling repo | mainCode/Investment_value.py:3-7, 73-77; mainCode/value_investment_lookup.py:2-8 | Path hacks, missing Gsheet, hard-coded ID at Investment_value.py:19 |
| Gmail SMTP | Functions and Libs/email_msg.py:11-16, 32-33 | Direct credentials and side effects |
| SEC/EDGAR | Test/Test_EDGAR.py:1-7 | Missing package/no fixture boundary |

## Path and packaging coupling

value_investment_lookup mutates sys.path for a sibling library and Py2GoogleDrive (mainCode/value_investment_lookup.py:1-8). Investment_value uses a Windows-style Py2GoogleDrive path (mainCode/Investment_value.py:1-7). expected_requirements adds ../Functions and Libs/ (Test/expected_requirements.py:1-5). Legacy directories are not packages; execution location is part of the API.

## Compatibility evidence

python3 -m compileall -q . failed on Python-2 print syntax in Functions and Libs/investing.py:74, Test/ETF_data.py:25 and Test/expected_requirements.py:16, plus the invalid backtick parameter in mainCode/Tradebill_Library.py:10. It emitted is-with-string-literal warnings from mainCode/stock.py:951 and value_investment_lookup.py:226, 239, 257, 275, 293. pyproject.toml:9-16 targets Python >=3.12 with no runtime dependencies, so it does not package legacy modules.

## Recommendation

Keep V2 provider-neutral (src/stocks_investment/interfaces/protocols.py:15-40), add adapters with timeout/auth/cache/provenance, and isolate legacy dependencies in a migration extra while generating offline fixtures.
