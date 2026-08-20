# Advanced statistical validation methodology

Wave E validates whether associations observed in persisted historical factor
research are credible enough to study further. It does not certify a factor as
profitable and does not optimize a strategy.

The V1 pipeline is:

1. freeze an immutable dataset manifest and source snapshots;
2. select observations by factor, universe, benchmark, currency and date;
3. create explicit overlapping or non-overlapping cohorts;
4. calculate cross-sectional rank IC separately on each research date;
5. summarize stability and decay without pooling incompatible horizons;
6. quantify uncertainty with seeded IID or moving-block bootstrap;
7. correct supplied hypothesis p-values within an explicit family;
8. evaluate only predeclared factor dependence/interactions and regime slices;
9. keep development, validation and out-of-sample windows disjoint;
10. persist the manifest, cohort membership, methodology parameters and final
    validation summary for deterministic read-back.

Every result must preserve factor version, universe, horizon, benchmark,
currency and cadence. Missing values are exclusions, never zero. Overlapping
forward returns are not independent observations. Synthetic tests establish
software correctness only; they provide no evidence of real-world alpha.

Detailed methods are documented in the sibling pages for datasets, sampling,
information coefficient, uncertainty, multiple testing, walk-forward,
factor dependence and robustness.
