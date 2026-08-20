# Factor dependence and interactions

E1G provides descriptive diagnostics over frozen factor observations. It does
not fetch data, fit weights, optimize a strategy, or claim causality.

## Identity and alignment

Each observation carries ticker, as-of date, factor name/version and universe.
Pairwise calculations join on `(ticker, as_of)` using keyed mappings. Input
ordering is irrelevant; duplicate keys, mixed factor identities, incompatible
universes and out-of-window dates are rejected. Missing or non-valid values are
excluded from the usable pair and are never converted to zero.

The reported coverage is `usable shared keys / union of keys`. The diagnostic
is valid only when the configured minimum usable sample is met.

## Correlation

`calculate_factor_dependence` reports tied-rank Spearman correlation. Ties use
average ranks. A constant factor has no defined correlation and should be
treated as not applicable by callers. The result retains factor versions,
universe, date window, eligible keys, shared sample size, coverage and status.

Correlation is descriptive association, not predictive proof or causality.

## Value × Quality interaction

`calculate_value_quality_interaction` accepts normalized Value and Quality
scores in `[0, 100]` and computes the predeclared equal-scale diagnostic:

`interaction = Value × Quality / 100`

The summary is the arithmetic mean over identity-matched valid pairs. This is
not a learned interaction, does not optimize weights and must not be read as a
return forecast.

## Contract note

The frozen `FactorObservation` contract does not carry universe identity. E1G
therefore uses the local immutable `FactorDependenceObservation` record for
this diagnostic. A future shared contract may add a canonical cohort/source
reference if multiple Wave E consumers need the same representation; no shared
contract was changed in E1G.
