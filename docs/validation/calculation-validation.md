# Independent calculation validation

## ACME Synthetic Holdings

The fixture is intentionally synthetic so the expected values can be audited without importing production formulas or depending on a vendor revision. Values are in USD; price and shares are point-in-time; revenue, EPS, net income, OCF, capex, NOPAT and invested capital are comparable TTM values; book value, debt, cash, assets and liabilities are point-in-time.

Hand calculations:

| Metric | Calculation | Expected |
|---|---|---:|
| Market cap | `50 × 100` | `5,000` |
| Enterprise value | `5,000 + 200 − 50` | `5,150` |
| Book value/share | `1,000 ÷ 100` | `10` |
| Current ratio | `400 ÷ 200` | `2` |
| P/E | `50 ÷ 4` | `12.5` |
| P/B | `50 ÷ 10` | `5` |
| Revenue growth | `(500 − 400) ÷ 400` | `25%` |
| EPS growth | `(4 − 3.2) ÷ 3.2` | `25%` |
| FCF | `120 − 40` | `80` |
| ROE | `100 ÷ 1,000` | `10%` |
| ROIC | `90 ÷ 1,150` | `7.8261%` |
| Graham number | `sqrt(22.5 × 4 × 10)` | `30` |

The test compares production output only for metrics currently supported by the B1 engine. Unsupported metrics are deliberately marked as coverage gaps rather than having expected values weakened to match `NOT_APPLICABLE`.

## B1.5 metric validation

The production engine now independently agrees with the ACME fixture for:

- Enterprise Value: `5,000 + 200 − 50 = 5,150`
- TTM P/E: `50 ÷ (1 + 1 + 1 + 1) = 12.5`
- Book Value: common equity `= 1,000`
- BVPS: `1,000 ÷ 100 = 10`
- P/B: `5,000 ÷ 1,000 = 5`
- Graham Number: `sqrt(22.5 × 4 × 10) = 30`
- Standard ROIC: `90 ÷ ((1,100 + 1,150) / 2) = 8%`

The simplified ROIC fixture remains separately labeled: `90 ÷ 1,150 =
7.8261%`. It is not treated as interchangeable with the standard average-capital
variant.

Pathological golden cases preserve negative EPS, negative book value, zero
equity, zero EPS, missing debt/cash, and cash greater than debt. The Graham trap
case uses EPS `−2` and BVPS `−5`; although their product is positive, the result
is explicitly `NOT_MEANINGFUL`.
