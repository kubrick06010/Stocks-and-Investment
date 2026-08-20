# Graham methodology

This C1 slice is pure and explainable: it consumes validated `MetricResult`
values and normalized `Fact` rows. It does not fetch data, score, rank, or
screen securities.

The historical identities are `graham_defensive_literal_v1` and
`graham_enterprising_literal_v1`. They preserve explicit cutoff criteria in
`GrahamThresholds` and emit one `CriterionResult` per criterion. Missing input
is `INSUFFICIENT_DATA`, while a non-meaningful metric is never coerced into a
pass or fail. The modernized identities use relaxed project assumptions and
different versions; they are not aliases and must be selected explicitly.

The validated upstream Graham Number is `sqrt(22.5 × TTM diluted EPS × BVPS)`
with both inputs strictly positive. Its interpretation here is only the
valuation ceiling `price <= Graham Number`, not a forecast.

Classic NCAV is `current_assets - total_liabilities`, selected point-in-time
at `as_of`. NCAV/share requires positive declared shares. The classic net-net
criterion passes at `price / NCAV per share <= 2/3`; negative NCAV is
`NOT_APPLICABLE`, while missing inputs remain `INSUFFICIENT_DATA`. No
liquidation discount or quality adjustment is inserted silently.

Margin of safety is `1 - price / intrinsic_value`, with a 33% default minimum.
Intrinsic value must be positive and price non-negative.

Ten-/five-year earnings, dividend continuity, size, debt-to-NCAV, and growth
history need an upstream history adapter; this workstream does not fabricate
those records from a single metric. No contract change request is needed.
