# Financial Metrics Specification

This specification is the implementation contract derived from the formula
audit. It is intentionally provider-neutral: adapters may use Yahoo, FMP,
EDGAR, or another source, but the normalized fields and period rules below
must hold before formulas run.

## Normalized inputs

Each statement record must include `period_start`, `period_end`, `filing_date`
(or public availability date), `fiscal_period`, `currency`, and `source`.
Income and cash-flow records are flows; balance-sheet records are snapshots.
Market records include `market_timestamp`, `price`, market cap if supplied,
and share counts. Monetary values are currency units, shares are counts, price
and per-share values are currency/share, ratios are x, and percentage outputs
are 0–100 percentage points.

Required normalized fields, where available:

`revenue`, `cost_of_revenue`, `gross_profit`, `operating_income`, `ebitda`,
`net_income`, `net_income_attributable_common`, `preferred_dividends`,
`basic_eps`, `diluted_eps`, `weighted_avg_basic_shares`,
`weighted_avg_diluted_shares`, `cash_and_equivalents`,
`short_term_investments`, `total_assets`, `total_liabilities`,
`common_equity`, `preferred_equity`, `goodwill`, `intangibles`, `total_debt`,
`current_assets`, `current_liabilities`, `operating_cash_flow`, and
`capital_expenditures`.

## Formula contract

| Metric | Formula | Period / point-in-time rule | Edge-case rule |
|---|---|---|---|
| Market cap | `price × shares` | Same market timestamp and share basis | Provider value may be used only with a known timestamp/basis. |
| Enterprise value | `market_cap + total_debt + preferred_equity + NCI − cash_and_equivalents` | Market fields at `as_of`; latest eligible balance snapshot | Missing components produce null; document excluded components. |
| Revenue | `revenue` | Reported statement period | Preserve fiscal dates and filing availability. |
| Gross profit | `revenue − cost_of_revenue` | Same flow period | Prefer validated reported field; null if required input absent. |
| Operating margin | `operating_income / revenue × 100` | Same period, generally TTM for valuation analysis | Null on zero revenue. |
| Net margin | `net_income_attributable_common / revenue × 100` | Same period, generally TTM | State continuing-operations policy; null on zero revenue. |
| ROA | `net_income / average(total_assets) × 100` | TTM income; assets at beginning/end boundary | Null or “not meaningful” for zero/cross-zero average assets. |
| ROE | `net_income_attributable_common / average(common_equity) × 100` | TTM income; equity at beginning/end boundary | Negative/cross-zero equity is not a conventional return. |
| Tangible ROE / ROTS | `net_income_attributable_common / average(common_equity − goodwill − intangibles) × 100` | Same TTM and boundary dates | Null if tangible equity is unavailable or crosses zero. |
| Revenue/share | `period_revenue / weighted_avg_diluted_shares` | Same flow period and share basis | Never use current shares for historical flow periods. |
| Basic EPS | `income_available_common / weighted_avg_basic_shares` | Same reported flow period | Do not substitute consolidated income or point-in-time shares. |
| Diluted EPS | `income_available_common / weighted_avg_diluted_shares` | Same reported flow period | Apply source dilution rules; retain provider EPS if reconciled. |
| TTM EPS | `sum(last 4 comparable quarterly EPS)` or recompute from TTM numerator/denominator | Quarters end on/before `as_of` | Exactly four quarters; reject gaps or label annual fallback explicitly. |
| Quarterly revenue growth | `(Q_t / Q_{t-4} − 1) × 100` | Comparable fiscal quarters | Null for zero/missing comparator; QoQ is a separate metric. |
| Quarterly earnings growth | `(EPS_t / EPS_{t-4} − 1) × 100` | Comparable fiscal quarters | Sign changes and zero comparator require a qualitative/null result. |
| Price/sales | `price / TTM revenue_per_share` or `market_cap / TTM revenue` | Price at `as_of`; TTM ends ≤ `as_of` | Null for non-positive/zero revenue. |
| Price/book | `price / common_equity_per_share` | Price at `as_of`; latest eligible balance snapshot | Same common share basis; negative/zero book requires explicit policy. |
| EV/revenue | `EV / TTM revenue` | Same `as_of` and TTM boundary | Null for zero/negative revenue. |
| EV/EBITDA | `EV / TTM EBITDA` | Same `as_of` and TTM boundary | Null for zero/negative EBITDA; label adjusted vs unadjusted. |
| Forward P/E | `price / forward_diluted_EPS` | Forecast vintage available by `as_of`; declared horizon | Null for absent/non-positive forecast EPS. |
| PEG | `P/E / expected_EPS_growth_percent` | Same forecast horizon and vintage | Growth is percentage points (10 = 10%); null for ≤0 growth. |
| Book value | `total_assets − total_liabilities − preferred_equity` | Balance-sheet date | If tangible book is needed, expose separate `tangible_book_value`. |
| Tangible book value | `common_equity − goodwill − intangibles` | Balance-sheet date | Do not derive from current assets/current liabilities. |
| Book value/share | `common_equity / common_shares_outstanding` | Same balance date and share basis | Null for zero shares; preserve negative book value. |
| Total cash | `cash_and_equivalents [+ short_term_investments]` | Balance-sheet date | Inclusion of investments must be a configured definition. |
| Total cash/share | `total_cash / shares_outstanding` | Same balance date and share basis | Null for zero/missing shares. |
| Total debt | `short_term_debt + current_LT_debt + long_term_debt` | Balance-sheet date | Lease inclusion must be configured; do not use total liabilities. |
| Debt/equity | `total_debt / common_equity` | Same balance date; ending snapshot | Negative equity is flagged, not coerced. |
| Current ratio | `current_assets / current_liabilities` | Same balance-sheet date | Null on zero/missing current liabilities. |
| Operating cash flow | `reported_net_cash_from_operating_activities` | Same cash-flow period | Do not infer from net income without full reconciliation. |
| Levered FCF | `operating_cash_flow − capital_expenditures` | Same cash-flow period | Normalize capex sign once; do not double-subtract negative capex. |

## As-of selection and alignment

For a requested valuation `as_of`, select only records with
`filing_date ≤ as_of`. Select the latest eligible balance snapshot for
point-in-time inputs. Select the latest four comparable quarterly flow
records ending on or before `as_of` for TTM. If a filing restates an earlier
period, retain the source’s filing date and make the restatement policy
explicit; never silently use a future restatement in historical backtests.

Before dividing, validate that both operands have compatible currency, share
basis, fiscal boundary, and source availability. A failed validation returns
`null` plus a machine-readable reason such as `MISSING_INPUT`,
`ZERO_DENOMINATOR`, `NEGATIVE_NOT_MEANINGFUL`, `PERIOD_MISMATCH`, or
`LOOKAHEAD_DATA`.

## Legacy migration map

The legacy methods and their disposition are:

- `enterpriseValue`, `EVperRevenue`: retain names but replace current-profile
  market cap reuse and statement-row denominators with aligned `as_of`/TTM
  inputs (`stock.py:167-208`).
- `bookValue`, `BookValuePerShare`, `bookValuePerShare`: replace the current-
  asset/current-liability calculation and market-cap denominator
  (`stock.py:217-256`, `534-554`).
- `trailingEPS`, `trailingPE`: use four quarters and period-matched diluted
  EPS (`stock.py:496-532`).
- `RevenuePerShare`, `EPS`: use period-weighted shares and income available to
  common (`stock.py:352-411`).
- `currentRatio`: retain the direct formula, adding denominator and schema
  validation (`stock.py:336-350`).
- `priceSalesRatio`, `pricePerBookValue`: retain only after period/share-basis
  alignment (`stock.py:263-296`, `594-607`).

## Minimum acceptance tests

Implementations must test: four-quarter TTM selection; annual versus quarterly
period labels; filing-date/as-of filtering; missing and zero denominators;
negative EPS/equity/revenue; preferred dividends/equity; goodwill and
intangibles; stock splits; current versus weighted-average shares; capex sign;
market price versus balance-sheet date alignment; and provider aliases such as
`Revenue` versus `totalRevenue`. Each test should assert both numeric output
and units/period metadata.

## Wave B1 implementation contract

The B1 engine lives in `stocks_investment.fundamentals.engine`. It consumes
immutable `Fact` values and an optional immutable `MarketSnapshot`; it performs
no provider calls, persistence, logging, clock reads, scoring, or strategy
decisions. `calculate_metric` returns a `MetricResult` with `status`, `as_of`,
`period`, `units`, `currency`, `inputs`, `version`, and `notes` on every path.

The initial coherent baseline is: market cap, TTM revenue, TTM diluted EPS,
gross profit, operating margin, net margin, ROA, ROE, current ratio,
debt/equity, TTM operating cash flow, and levered FCF. TTM calculations require
four comparable quarterly records ending on or before `as_of`; future filings
are excluded. Capex is treated as a positive outflow by the FCF calculation,
so a source that reports capex as negative is normalized with `abs` exactly once.

Statuses are machine-readable: `missing`, `zero_denominator`,
`negative_not_meaningful`, `not_meaningful`, `not_applicable`, `stale`, and
`insufficient_history`, in addition to `valid` and `period_mismatch`. Invalid
results always carry `value=None`; a numeric zero is therefore preserved as a
valid input rather than confused with missing data. The local status enum is
intentionally not added to the shared domain model during B1.

## B1.5 financial correctness contract

| Identifier | Definition | Period/share convention | Semantics |
|---|---|---|---|
| `enterprise_value_v1` | market cap + total debt + preferred equity + NCI − cash | market price at `as_of`; latest eligible balance facts | debt/cash are required; absent preferred/NCI are explicitly noted as a zero approximation |
| `price_to_earnings_ttm_v1` | price ÷ sum of four comparable quarterly diluted EPS facts | TTM EPS; price at `as_of` | EPS ≤ 0 is `NOT_MEANINGFUL`; zero is not missing |
| `book_value_common_equity_v1` | common shareholders’ equity | latest eligible balance snapshot | negative equity is preserved as the underlying book value |
| `book_value_per_share_v1` | common equity ÷ declared shares outstanding | balance date; explicit `MarketSnapshot.share_basis` | missing/zero/non-positive shares are not substituted |
| `price_to_book_common_equity_v1` | market cap ÷ common equity | price/shares at `as_of`, equity at eligible balance date | equity ≤ 0 is `NOT_MEANINGFUL` |
| `graham_number_v1` | `sqrt(22.5 × TTM EPS × BVPS)` | four-quarter TTM EPS and balance-date BVPS | both inputs must be strictly positive; two negatives never produce a valid result |
| `roic_nopat_avg_invested_capital_v1` | NOPAT ÷ average(beginning, ending invested capital) × 100 | declared NOPAT and beginning/end capital | average capital must be positive |
| `roic_simplified_v1` | NOPAT ÷ point-in-time invested capital × 100 | fallback only when beginning/end capital are unavailable | explicitly labeled simplified |

`Fact.provenance` is the canonical `DataProvenance` object. The
`fact_from_observation` adapter preserves that object instead of creating a
parallel provenance model. `MetricResult.source_provenance` retains references
to the evidence used by the calculation. The result `version` and `inputs`
identify both methodology and source dependencies.

Required semantic distinctions are tested: missing denominator → `MISSING`,
zero/negative EPS → `NOT_MEANINGFUL` for P/E, zero/negative common equity →
`NOT_MEANINGFUL` for P/B, and reported zero values remain valid zeros.
