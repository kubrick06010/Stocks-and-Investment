# Formula audit

Classification is based on the legacy implementation, not the method name. `LEGACY_WRONG` means the implemented arithmetic is materially not the named metric; `LEGACY_AMBIGUOUS` means inputs or period/share policy are not defined well enough to certify.

| Metric | Legacy location | Classification | Finding |
|---|---|---|---|
| Market cap | `stock.py:488-495` | LEGACY_AMBIGUOUS | delegated to provider; no timestamp/share basis |
| Enterprise value | `stock.py:159-178` | LEGACY_PARTIALLY_CORRECT | equity value + debt − cash, but no preferred/minority/investment policy and current profile is reused across periods |
| P/E | `stock.py:516-531` | LEGACY_AMBIGUOUS | TTM EPS is only three quarters and price date is current/latest |
| Forward P/E | `stock.py:181-187` | NOT_IMPLEMENTED | raises exception |
| PEG | `stock.py:190-194` | NOT_IMPLEMENTED | raises exception |
| P/S | `stock.py:222-253` | LEGACY_PARTIALLY_CORRECT | price/revenue-per-share shape is valid, but inputs are inconsistently indexed and period/share basis is unclear |
| P/B | `stock.py:559-574` | LEGACY_AMBIGUOUS | provider key/period policy unclear |
| EV/Revenue | `stock.py:202-220` | LEGACY_PARTIALLY_CORRECT | arithmetic is valid when inputs align; recursive/missing handling and units are unsafe |
| EV/EBITDA | `stock.py:255-265` | NOT_IMPLEMENTED | no calculation |
| Book value | `stock.py:194-214` | LEGACY_WRONG | computes current assets − intangibles − current liabilities, not common equity or a complete tangible book value |
| BVPS | `stock.py:216-220`, `:548-557` | LEGACY_WRONG | annual path divides book value by market cap; quarterly path uses current shares without historical policy |
| EPS | `stock.py:365-415` | LEGACY_PARTIALLY_CORRECT | net income/shares is a rough proxy; uses first/current outstanding shares, not weighted-average diluted shares; dividends are read then ignored |
| TTM EPS | `stock.py:500-518` | LEGACY_WRONG | sums three quarters (`range(i, i+3)`), not four or FY/YTD reconciliation |
| Revenue/share | `stock.py:337-372` | LEGACY_AMBIGUOUS | revenue field and shares are not guaranteed period-matched |
| Current ratio | `stock.py:314-330` | LEGACY_CORRECT | arithmetic is current assets/current liabilities, subject to missing/zero handling |
| Debt/equity | — | NOT_IMPLEMENTED | `debtPerCurrentRatio` is debt/current ratio, not debt/equity |
| ROA/ROE/ROIC | — | NOT_IMPLEMENTED | no identified implementation |
| Gross/operating/net margin | — | NOT_IMPLEMENTED | no identified implementation |
| FCF | — | NOT_IMPLEMENTED | no identified implementation |
| Owner earnings | — | NOT_IMPLEMENTED | no identified implementation |
| Graham number | `stock.py:575-594` | LEGACY_PARTIALLY_CORRECT | classic parameterized square-root shape, but negative inputs and invalid TTM/BVPS are not guarded |
| NCAV/net-net | — | NOT_IMPLEMENTED | no implementation |
| Dividend continuity | `stock.py:435-473`, `:718-742` | LEGACY_PARTIALLY_CORRECT | annual presence check exists, but uses current date, does not distinguish declared/paid, and can miss gaps/partial years |
| Earnings stability | `value_investment_lookup.py:102-121` | LEGACY_AMBIGUOUS | count and EPS source are not guaranteed 10 comparable annual periods; missing values use truthiness |
| Earnings growth | `value_investment_lookup.py:125-168` | LEGACY_WRONG | beginning is a three-period sum while end selection changes with length; growth denominator can be zero/negative and threshold semantics are unclear |

## Release rule

No legacy formula is promoted into V2 without a typed definition, a hand-calculated fixture, explicit period/share/currency policy, and edge-case tests. Legacy outputs may be retained only as labeled regression observations.
