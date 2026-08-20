# Factor robustness and turnover adjustment

`robustness_v1` evaluates persisted factor outcomes in externally supplied,
predeclared year or regime slices. The engine never infers regimes after
seeing returns. Each observation is joined to its label by ticker and date;
missing labels and missing outcomes remain visible in coverage counts.

Slices report sample size, coverage, mean/median excess return and a
descriptive tied-rank association. Pooled slice correlation may conceal
date-level instability, so cross-sectional IC-by-date remains the preferred
primary diagnostic.

Turnover adjustment uses explicit economics:

```text
transaction cost = gross traded notional × transaction cost rate
cost return impact = transaction cost / portfolio capital
net factor spread = gross factor spread - cost return impact
```

Gross traded notional counts the convention supplied by the validated
backtest layer. This module does not reconstruct trades, infer costs, optimize
regimes, claim causality or estimate statistical significance.
