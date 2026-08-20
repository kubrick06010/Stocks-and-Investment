# Quality and forensic factors

Versioned calculations in `strategies.quality` consume normalized, validated
fundamental inputs. They are pure calculations: no provider calls, no
look-ahead filtering, no missing-value imputation, and no portfolio scoring.
The caller is responsible for supplying facts available by `as_of` and for
aligning periods and share bases.

## Piotroski F-Score — `piotroski_f_score_v1`

The nine equal binary signals are: positive ROA, positive operating cash flow,
improving ROA, operating cash flow greater than net income, lower total debt,
improving current ratio, no share dilution, improving gross margin, and
improving asset turnover. The result is a 0–9 point total only when all nine
criteria are decidable; otherwise the total is null and each criterion retains
its own insufficient-data status. This is the original discrete signal design,
not a normalized 0–100 score.

## Altman Z-Score — `altman_z_score_v1`

The variant is mandatory in the result identity:

* `original_manufacturing`: 1.2 WC/TA + 1.4 RE/TA + 3.3 EBIT/TA + 0.6 MV equity/TL + 1.0 sales/TA.
* `private_company`: 0.717 WC/TA + 0.847 RE/TA + 3.107 EBIT/TA + 0.420 BV equity/TL + 0.998 sales/TA.
* `non_manufacturer`: 6.56 WC/TA + 3.26 RE/TA + 6.72 EBIT/TA + 1.05 BV equity/TL; it has no sales term.

Published cutoffs are not applied here: industry, geography, accounting
policy, private/public status, and period definition affect interpretation.
Negative or zero denominators are not converted into meaningful ratios, and
the market-equity variant must not be used for private companies.

## Beneish M-Score — `beneish_m_score_v1`

The eight indices are DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, and TATA. The
published linear expression is `-4.84 + .92 DSRI + .528 GMI + .404 AQI + .892
SGI + .115 DEPI - .172 SGAI + 4.679 TATA - .327 LVGI`. GMI uses gross-profit
margin; LVGI uses leverage relative to total assets; TATA is `(net income −
operating cash flow) / total assets`. Two aligned annual periods are required.
The output is a screening statistic, not a probability or accusation, and it
is sensitive to classification, acquisitions, leases, foreign-currency
translation, and industry business models.

All three factors are especially fragile for financial institutions, insurers,
REITs, asset-heavy cyclicals, early-stage loss makers, acquisitive companies,
and firms with material restatements or custom taxonomy mappings. Use the
source filing, accounting policy, and point-in-time availability metadata in
parallel with these observations.
