# Legacy risk register

| ID | Risk | Severity | Evidence | Control |
|---|---|---|---|---|
| L-01 | Legacy tree does not compile under Python 3 | Critical | compileall; investing.py:74; ETF_data.py:25; expected_requirements.py:16; Tradebill_Library.py:10 | Isolate and port characterized behavior |
| L-02 | Hidden network I/O in object construction | Critical | mainCode/stock.py:963-1005, 1568-1576 | Inject providers and cache raw responses |
| L-03 | Provider/schema drift unchecked | High | mainCode/stock.py:958-961, 744-827 | Typed adapters, status checks and fixtures |
| L-04 | Look-ahead/survivorship bias | Critical | FTP/Wikipedia universes, mainCode/stock.py:1851-1905 | Version universes and enforce availability |
| L-05 | Per-share valuation formulas suspect | Critical | book-value path divides by mktCap, mainCode/stock.py:242-255; undefined timeline at :583-590 | Golden formulas with units/denominator checks |
| L-06 | Inconsistent schemas/containers | High | mainCode/stock.py:236-254, 336-372, 398-409 | Normalize by ticker/period |
| L-07 | Missing/zero/error states conflated | High | -1 at mainCode/stock.py:180-181; truthiness at :521-525; broad catches in value_investment_lookup.py:22-27 | Explicit status enum |
| L-08 | Technical indicators incomplete/broken | High | RSI mismatch :1191-1214; ATR/PPO pass :1216-1219, :1249-1252; Bollinger undefined names :1227-1247 | Pure formula tests |
| L-09 | Strategy module unreachable | High | syntax error mainCode/Tradebill_Library.py:10; channelTrade prints at :73-81 | Reimplement behind score contract |
| L-10 | Portfolio math is not a return methodology | Critical | share mutation Investment_value.py:24-71; principal/ROI :147-163, :238-243 | Ledger, TWR, XIRR and fixtures |
| L-11 | Removed pandas APIs | High | DataFrame.append Investment_value.py:128-129; pandas.Panel :140-145 | Replace after formula characterization |
| L-12 | Missing modules/files/path hacks | High | Gsheet imports Investment_value.py:6 and value_investment_lookup.py:8; missing ticker_ETF.txt ETF_data.py:5-8 | Package and inject storage |
| L-13 | Secret exposure | Critical | SMTP password Functions and Libs/email_msg.py:63-64; spreadsheet ID Investment_value.py:19 | Rotate, remove literals, env-only dry-run |
| L-14 | No reproducibility boundary | High | live top-level probes test_fundamentals.py:5-24 and Yahoo_datareader.py:4-27 | Offline fixtures and provenance |
| L-15 | Identity comparison controls screen branch | Medium/High | value_investment_lookup.py:226-293 | Equality plus branch tests |
| L-16 | Stale install/docs | Medium | README:9-20 versus ROADMAP.md:1-24 | One canonical guide |

## Triage order

1. Freeze the legacy boundary and stop implicit live-service execution.
2. Generate offline fixtures and golden cases for prices, statements, screening and cash flows.
3. Port one vertical slice into V2 typed/provider interfaces, then quarantine dead script roots.
