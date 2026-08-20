# Multiple-testing correction V1

`multiple_testing_v1` corrects already supplied, valid p-values. It does not
generate test statistics or p-values, and it does not claim statistical
significance by itself.

## Family identity

One call operates on exactly one non-empty `family_id`. A family is the set of
hypotheses to which the correction applies. Mixing families changes the
multiple-testing denominator and is rejected. Hypotheses must also agree on
`alpha` and correction method unless a caller explicitly overrides those
parameters for the complete family.

Results are sorted by `(raw_p_value, hypothesis_id)`, so ties are deterministic
and independent of input order. The output retains each hypothesis identity and
family identity.

## Methods

Benjamini-Hochberg controls the false-discovery-rate procedure by assigning the
ranked value `min(1, p_i * m / i)` and applying a reverse cumulative minimum.
Rejection uses the adjusted p-value `<= alpha`.

Holm-Bonferroni controls the family-wise procedure using ranked values
`(m - i + 1) * p_i`, capped at one, followed by a forward cumulative maximum.
Rejection also uses `adjusted_p_value <= alpha`.

`NONE` is an explicit no-correction mode: adjusted p-values equal raw p-values.
It is useful for transparent baselines but does not correct for multiplicity.

Alpha must be finite and strictly between zero and one. Raw p-values must be
finite and in `[0, 1]`; missing, non-finite, or invalid values are errors rather
than zeros. Adjusted values are bounded in `[0, 1]` and monotone in corrected
rank order.

The implementation is deterministic and pure. It does not access providers,
storage, current data, or external services. No p-value, confidence claim, or
causal interpretation is inferred by this module.
