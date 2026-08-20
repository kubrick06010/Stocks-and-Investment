# Legacy-to-V2 mapping

| Legacy | V2 | Migration policy |
|---|---|---|
| `stock` façade | provider adapters + snapshot service | no direct port |
| Yahoo/FMP dicts | normalized observations | retain raw payload and mapping version |
| `Fundamental_Analysis` | fundamentals calculators | formulas revalidated |
| `Technical_Analysis` | technical series functions | pure, tested, no plotting side effects |
| defensive screen | versioned value strategy | criterion-level explanations |
| Google Sheets book | transaction import adapter | CSV first; Sheets optional |
| `Investment_value` plots | portfolio ledger/analytics | replace return math |
| email side effects | report/export integration | remove from core |
