# Legacy feature map

| Intent | Evidence | Formula/behavior | Status | V2 destination |
|---|---|---|---|---|
| Historical prices | mainCode/stock.py:1578-1595 | Yahoo OHLCV; optional weekly aggregation | Remote; start_date bug | MarketDataProvider/provenance |
| Weekly candles | mainCode/stock.py:1597-1636 | high=max, low=min, open=first, close=last, volume=sum | Manual/incomplete-week assumptions | Tested transform |
| Statements/ratios | mainCode/stock.py:112-155, 744-827 | Yahoo/FMP dictionaries | Mutable provider schema | Fundamental adapter |
| Enterprise value | mainCode/stock.py:167-188 | market cap + debt - cash | Intent salvageable; periods/units unverified | Versioned formula |
| Book value/share | mainCode/stock.py:217-255, 534-554 | current-assets approximation; one path divides by mktCap, another by shares | Inconsistent/high risk | Correct denominator/units |
| Revenue/share | mainCode/stock.py:352-372 | revenue / outstanding shares | Index/container assumptions | Period-aligned metric |
| EPS | mainCode/stock.py:374-411 | net income / one share-count value | Dividends iterated but ignored | Golden EPS formula |
| Trailing EPS/PE | mainCode/stock.py:496-532 | quarterly EPS sum; close / TTM EPS | Off-by-one/field inconsistencies | TTM by period/as-of |
| Dividend continuity | mainCode/stock.py:612-652 | one dividend year at a time | Current FMP/order assumptions | Corporate-action adapter |
| Defensive value screen | value_investment_lookup.py:11-182 | price, ratios, PE, PB, revenue, EPS stability/growth, dividends | Philosophy clear; thresholds need versioning | strategies/value |
| Universe screening | value_investment_lookup.py:220-327 | current FTP/Wikipedia lists and ETF filters | Survivorship and identity comparison | Versioned UniverseProvider |
| Graham number | mainCode/stock.py:561-581 | sqrt(PE_max*PB_max*TTM-EPS*book-value/share) | Missing-field/unit risks | Formula contract |
| Graham price | mainCode/stock.py:583-592 | close / Graham number * 100 | Undefined timeline | Named signal |
| SMA/EMA/MACD | mainCode/stock.py:1085-1149 | slice average, K=2/(period+1), EMA difference/histogram | Alignment unvalidated | Pure indicators |
| RSI | mainCode/stock.py:1191-1214 | average gain/loss formula | Default Close rejected by lowercase check | Canonical indicator |
| Impulse system | mainCode/stock.py:1297-1459 | candle color from EMA/MACD derivatives | Plot side effect/fragile offsets | Signal plus renderer |
| WSB momentum score | Tradebill_Library.py:18-71 | impulse + EMA zone + MACD pattern + direction | File syntax-invalid | Versioned score |
| Investment ledger | Investment_value.py:24-71 | purchases add shares, sales subtract, mark to close | String/date parsing fragile | Ledger/positions |
| Principal/ROI charts | Investment_value.py:147-178, 186-265 | value-principal; percent difference/principal | Not TWR/XIRR; removed APIs | Cash-flow analytics |
| Compounding | Functions and Libs/investing.py:20-31 | P=P0*(1+r)^t; active adds P0 each period | Salvageable pure formulas | Golden tests |
| Grid optimizer | Functions and Libs/investing.py:33-57 | grid of price/rate and absolute ROI | month_income unused; xrange | Contract or remove |
| Email | Functions and Libs/email_msg.py:9-33 | SMTP STARTTLS/login/sendmail | Secret/side effect | Optional notifier |
| Crypto history | mainCode/stock.py:1798-1849 | CryptoCompare minute pagination | Remote/Python-2 assumptions | Separate adapter/defer |

## Preservation rule

Preserve philosophy and formulas only after units, period/as-of semantics, missing-data behavior and golden tests are explicit. Do not preserve unfinished/deprecated methods (mainCode/stock.py:210-214, 258-261, 311-314, 435-440, 556-559, 1768-1770) or the syntax-invalid Tradebill library.
