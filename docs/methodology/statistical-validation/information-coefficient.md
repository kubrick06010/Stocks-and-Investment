# Cross-sectional information coefficient

`information_coefficient.py` implements descriptive, point-in-time
cross-sectional Spearman IC over frozen `FactorOutcomeObservation` records.

For each research date, only securities with both a factor score and a usable
future excess return participate. Missing values are excluded from the
calculation and remain visible through the date-level sample size and status;
they are never converted to zero. Ties use average ranks. Securities are
keyed by ticker and duplicate tickers within one date are rejected.

The default minimum is ten usable securities per date, matching the statistical
validation specification. Smaller cross-sections produce
`INSUFFICIENT_SAMPLE` (or `INSUFFICIENT_COVERAGE` when missing outcomes caused
the shortfall), not a fabricated correlation.

Stability summaries aggregate valid date-level IC values with equal weight per
date and report mean, median, population volatility and the fraction of dates
with positive IC. This is deliberately not a pooled correlation and makes no
significance claim.

IC decay accepts a separate observation set and frozen `ValidationCohort` for
each horizon. Factor version, universe, cadence, currency and benchmark must
remain identical while the horizon changes. Horizons are never pooled,
interpolated or silently mixed. If an outcome window is incomplete, the
corresponding observation is unavailable rather than imputed.

The returned statistics are descriptive. Overlapping horizons can share future
returns, so date-level observations need not be independent. The module does
not calculate p-values, confidence intervals or causal effects.
