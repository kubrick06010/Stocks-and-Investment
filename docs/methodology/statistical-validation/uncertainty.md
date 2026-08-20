# Bootstrap uncertainty intervals

Wave E.1D provides deterministic percentile bootstrap intervals over an
ordered sequence of dated numeric observations. The implementation is pure
Python and does not contact providers or persist results.

## Contract

`bootstrap_confidence_interval` accepts observations as `(date, value)` pairs,
an optional statistic, an explicit `BootstrapMethod`, confidence level,
resample count and integer seed. The returned `ConfidenceInterval` is the
frozen domain contract and records the method, configuration and estimate.

Inputs must contain at least two observations, strictly increasing dates and
finite numeric values. A statistic must return one finite numeric value for
the original and every resampled sequence. Empty samples, invalid confidence
levels, non-positive resample counts, unordered dates, non-finite values and
invalid block sizes fail explicitly. No missing value is converted to zero.

## IID bootstrap

IID resampling draws individual observations with replacement until the
original sample length is reached. The seeded `random.Random` instance makes
reruns reproducible. Dates establish input order but are not resampled as
separate values; the statistic receives the corresponding numeric sequence.

## Moving-block bootstrap

Moving-block resampling requires `1 <= block_size <= sample_size`. It samples
contiguous blocks from the chronologically ordered input, appends blocks until
the original length is reached, and truncates the final block. Order inside
each block is preserved. Boundaries between independently sampled blocks can
be discontinuous; this is the intended V1 approximation.

The method does not fit a time-series model and should not be interpreted as
proof that dependence has been fully modeled. Block size is a methodology
parameter and must be recorded by callers with the resulting interval.

## Interval construction

The estimate is the statistic on the supplied sample. Lower and upper bounds
are the linearly interpolated empirical percentiles at
`(1-confidence)/2` and `1-(1-confidence)/2` of the bootstrap statistics.
Because the frozen domain contract requires the reported interval to contain
the estimate, a finite-sample percentile bound is expanded to the estimate
when random resampling produces a one-sided bound. This is most relevant for
very small samples and is recorded as a contract-preserving convention, not
as evidence of additional precision.
This module intentionally does not calculate p-values or make significance
claims. Small samples remain mathematically computable but should be treated
as low-information evidence by the surrounding validation workflow.
