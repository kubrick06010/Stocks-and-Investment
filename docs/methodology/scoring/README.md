# Scoring methodology

The scoring package accepts only frozen `FactorObservation` values. It does not
fetch data, calculate raw metrics, apply investment rules, or identify tickers.
Those concerns remain in their owning workstreams.

## Normalization

`LinearScale(lower, upper, higher_is_better)` maps a finite input to 0..100:

`100 * clamp((value - lower) / (upper - lower), 0, 1)`

The result is reversed when lower values are better. Bounds are explicit and
versioned. Clipping makes out-of-range values deterministic; it does not hide
missing values. A non-valid observation remains unavailable and is never
converted to a zero score.

## Factor scores

`score_factor` filters observations after the requested `as_of` date, normalizes
each eligible valid observation, and takes their arithmetic mean. The original
observations are retained in canonical order for explanation and auditability.
No eligible valid observation produces a score with a non-valid status.

## Composite scores and missing data

`compose` sorts factor components by name, validates unique non-negative weights,
and records the exact weights and selected `MissingDataPolicy` in
`CompositeScore`.

| Policy | Semantics |
| --- | --- |
| `FAIL` | Any unavailable factor makes the final score unavailable. |
| `IGNORE_AND_RENORMALIZE` | Use available factors and divide by their weights only. |
| `PENALIZE` | Use all configured weight; unavailable factors contribute zero. |
| `INSUFFICIENT_DATA` | Any unavailable factor makes the final score unavailable and marks insufficient history. |

All returned scores are in 0..100. Factor and strategy versions are explicit in
the result; the default factor version includes the normalization identity.
