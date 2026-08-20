# Wave E.0 — Statistical Validation Methodology

Status: design guidance only. This document defines research methodology and
acceptance criteria; it does not define production APIs or authorize Wave E
implementation.

## Purpose and scope

Wave D records factor scores at an as-of date and later outcome observations.
Wave E must determine whether observed associations are credible, stable and
useful after accounting for dependence, turnover, selection and multiple tests.
The unit of evidence is the persisted historical observation, never a factor
value recomputed with current data.

Every analysis must retain, at minimum:

- factor name and methodology version;
- research run and as-of date;
- ticker and historical universe/cohort identity;
- outcome horizon, return convention, currency and benchmark;
- eligibility, usable observations and exclusions with reasons;
- whether observations overlap in time;
- methodology version and analysis parameters.

Results are associations, not proof of causation or investment advice.

## Cohort identity and minimum data semantics

An efficacy cohort is homogeneous in factor version, universe definition,
benchmark, currency/base-return convention, outcome horizon and sampling
cadence. Incompatible observations must be rejected or split into named
cohorts. They must never be silently pooled.

An observation is **eligible** when its research artifact was available at the
research date, the security belonged to the declared universe, and the factor
score has a valid status. It is **usable** only when the complete forward
outcome window and benchmark window exist, are currency-compatible, and have a
valid status. Missing, stale, not-meaningful and incomplete observations are
excluded with explicit counts; they are not zero returns.

Coverage is:

```text
usable observations / eligible observations
```

Coverage must be reported alongside every estimate. A practical default is to
return `INSUFFICIENT_DATA` when a cohort has fewer than 30 usable stock-date
observations, fewer than 10 distinct securities, or fewer than 5 distinct
research dates. These are governance thresholds, not claims of universal
statistical validity. For quantile spreads, require at least 5 observations
per bucket and report the number of distinct dates and securities. Small
samples may still support data-quality tests, but not persuasive efficacy
claims.

## Non-overlapping cohorts

Forward returns sampled monthly at a 12-month horizon overlap heavily. One
company can therefore contribute many observations sharing most of the same
future path. Such observations are not independent replicates.

Report at least two views when data permits:

1. **Overlapping panel:** all eligible research dates, with dependence and
   overlapping-horizon limitations disclosed.
2. **Non-overlapping cohort:** select one observation per security per horizon
   window, or use annual/quarterly formation dates whose outcome windows do
   not overlap for the same security.

The selection rule must be deterministic and recorded. A non-overlapping
analysis improves interpretability but reduces sample size. It does not remove
cross-sectional dependence, universe changes, sector concentration or common
market shocks.

## Pooled versus cross-sectional IC

Let `s(i,t)` be a factor score and `r(i,t+h)` the later excess return.

### Pooled IC

Pooled Spearman IC ranks all usable stock-date pairs together. It answers:

> Across the entire sample, do higher scores tend to precede higher outcomes?

It is easy to compute but can be dominated by time, sector, universe and
market-regime composition. It must not be the only IC statistic.

### Cross-sectional IC

For each research date `t`, compute Spearman rank correlation across securities
available at `t`, then summarize the date-level ICs with mean, median, standard
deviation, hit rate and sample count. This is closer to the ranking decision
made by a cross-sectional screen and prevents dates with more securities from
automatically receiving more weight.

Require a minimum of 10 usable securities for a date-level IC; otherwise mark
that date unavailable. Report both equal-date and observation-weighted
summaries if both are used. Ties require a documented rank convention.

Cross-sectional IC follows the spirit of information-coefficient practice and
Fama–MacBeth-style date-by-date analysis. Standard errors must account for
time dependence; naive independent-observation errors are not sufficient.

## IC decay

For a fixed factor cohort, calculate IC at each supported horizon, for example
1M, 3M, 6M, 12M and 24M. Keep factor version, universe, benchmark and formation
rule fixed while changing only the outcome horizon.

Report:

- mean and median cross-sectional IC by horizon;
- IC volatility and positive-IC date hit rate;
- usable dates and observations;
- the sign and magnitude change from shorter to longer horizons.

Do not interpolate missing horizons or compare cohorts with different
eligibility. A declining IC is descriptive; it does not establish a causal
decay mechanism. Horizon estimates may share outcomes and must disclose that
dependence.

## Uncertainty and bootstrap methods

Point estimates must be accompanied by uncertainty intervals when sample size
allows. The interval method, resampling unit, seed policy and percentile or
studentized convention must be recorded.

### Ordinary bootstrap

An ordinary nonparametric bootstrap resamples independent units with
replacement. It is defensible for a deliberately constructed non-overlapping
cohort when residual dependence is acceptably small. The resampling unit should
normally be the security-date or security, as determined by the estimand, not
an arbitrary flattened row.

### Cluster and block bootstrap

Stock-date observations share time shocks and a security can recur over time.
Use clustered resampling by security, date, or a two-way scheme where the
estimand and data support it. For serially dependent panels, use time blocks or
a stationary bootstrap in the style of Politis and Romano. Moving-block and
stationary bootstrap choices must state block length and sensitivity analysis.

Block bootstrap is not automatically correct: common factors, changing
universe membership and cross-sectional dependence can remain. Compare
reasonable block lengths and report instability rather than selecting the most
favorable interval.

Bootstrap intervals do not repair look-ahead bias, survivorship bias, bad
cohort definitions or data-mined hypotheses. They quantify sampling uncertainty
conditional on the research design.

## Confidence intervals and inference

Use percentile or bias-corrected accelerated intervals only with a documented
resampling design. For mean returns, median returns, spreads and ICs, preserve
the analysis unit and dependence structure. For rank IC, bootstrap date-level
ICs when the research question concerns typical cross-sectional dates.

Avoid treating a confidence interval crossing zero as a binary truth test.
Report estimate, interval, sample, design and limitations together. Do not use
normal approximations for tiny cohorts or heavily skewed returns without a
robustness check.

If regression-based inference is later added, use heteroskedasticity and
autocorrelation-robust errors where justified, such as Newey–West for suitable
time-series settings. Robust standard errors cannot correct selection bias or
overlapping panel construction by themselves.

## Multiple-testing controls

Every tested factor, horizon, universe, subgroup, transformation and parameter
choice contributes to the research family. The full tested family and
selection process must be recorded before interpreting discoveries.

### Benjamini–Hochberg FDR

The Benjamini–Hochberg procedure controls expected false discovery rate under
its stated dependence assumptions. Apply it to a predeclared family of
hypotheses with clearly defined p-values and direction. State whether the
family is all factors, all factor-horizon pairs, or another defensible unit.
Do not call an unadjusted p-value significant after exploring many variants.

### Family-wise error rate

When even one false positive is costly, consider family-wise controls such as
Holm–Bonferroni. Westfall–Young resampling can preserve dependence when its
assumptions and computational design are justified. Family-wise controls are
often conservative and reduce power.

### Data-mining caveats

BH does not make a post-hoc, adaptively selected factor family independent.
White's Reality Check and Hansen's Superior Predictive Ability test are
conceptual references for evaluating data-snooped strategy performance, not
automatic approval for their assumptions. The project must preserve the full
candidate history and distinguish exploratory findings from confirmatory
tests. No factor should be promoted solely because it survived a favorable
subgroup or horizon search.

## Regime and stability analysis

Aggregate efficacy can hide instability. Partition observations using
predefined, reproducible labels such as calendar year, volatility regime,
market trend regime, valuation regime or expansion/recession proxy. Regime
definitions must use information available at the formation date or be clearly
declared post-hoc descriptive labels.

For each regime report sample, coverage, mean/median excess return, IC,
dispersion, hit rate and turnover. Compare signs and rank ordering across
regimes. Require minimum support before publishing a regime estimate; otherwise
mark it descriptive/insufficient. Do not choose regime boundaries after seeing
which split produces the strongest result without labeling that analysis
exploratory.

Stability means more than a positive full-sample mean. Evaluate:

- sign consistency across dates and regimes;
- rolling or expanding estimates;
- sensitivity to removing the best and worst observations;
- stability across plausible universes and horizons;
- concentration in a few securities, sectors or dates.

## Turnover-adjusted efficacy

A factor can rank future returns yet be economically unattractive after
trading. Pair factor efficacy with a specified portfolio rule: rebalance
cadence, selection size, weighting, liquidity assumptions, price adjustment,
transaction-cost model and capacity limitations.

Report gross factor spread and net spread after costs, plus turnover, traded
notional, cost rate and coverage. Keep factor signal efficacy separate from
portfolio implementation efficacy. A factor-level return cannot be converted
to net portfolio performance without an explicit construction rule.

Turnover conventions must be explicit, for example half-turnover based on
absolute target-weight changes versus gross buys-plus-sells. Transaction costs
must be applied to the same declared notional convention. Include sensitivity
to plausible cost rates, but do not choose the rate that flatters the factor.

## Factor correlation and redundancy

Measure redundancy using persisted, date-aligned factor scores rather than
raw provider fields. Candidate diagnostics include Pearson correlation for
linear association, Spearman correlation for rank association, overlap of top
quantiles and conditional correlation after controlling for date or sector.

Use the same cohort, dates, missing-data policy and score versions. Report
effective sample and missingness. High correlation does not prove that one
factor is useless; low correlation does not prove incremental value. Test
incremental efficacy out of sample, and distinguish information overlap from
causal overlap.

## Factor interactions

Interactions such as Value × Quality can be studied through predeclared
double sorts, conditional spreads or cross-sectional regressions. Define bins,
breakpoints, minimum cell counts and missing-data rules in advance. A 2×2
sort should report every cell, not only the best cell.

Interactions multiply the number of hypotheses and therefore the multiple-test
family. Do not optimize weights or interaction thresholds on the evaluation
period. Interpret interaction patterns as exploratory until confirmed on a
fresh out-of-sample period.

## Development, validation and out-of-sample periods

Separate the historical timeline into:

- **development/train:** define or tune a methodology;
- **validation:** choose among predeclared alternatives and freeze the final
  specification;
- **out-of-sample:** evaluate the frozen specification once or under an
  explicitly documented monitoring protocol.

The split must be chronological. Never use future outcomes, future universe
membership or later factor versions when defining an earlier specification.
If the validation set is used repeatedly, it becomes development data and a
new holdout is required.

Persist the methodology version, split dates, candidate family, exclusions,
selection rationale and final freeze date. Do not report an out-of-sample
estimate when the specification was changed after inspecting it.

## Walk-forward validation

Walk-forward evaluation repeats a temporal protocol:

```text
train/define on [past]
freeze methodology
evaluate the next interval
advance the boundary
repeat without rewriting prior results
```

Each fold must have a distinct information cutoff. Research data and outcomes
must be separated at the fold boundary. The factor version used in a fold is
immutable after evaluation. Aggregate fold results with the number of folds,
dates, securities, coverage, turnover, costs and any failed/insufficient fold.

Do not average fold metrics as though folds were independent if they overlap.
Report both fold distribution and aggregate economic chaining where relevant.
Walk-forward protects against temporal overfitting but cannot guarantee future
performance, eliminate regime change or correct a flawed economic definition.

## Scientific limitations and release rules

Wave E statistical validation must explicitly disclose:

- look-ahead and survivorship exposure;
- delisting and missing-outcome treatment;
- overlapping horizons and dependence;
- small samples and unstable quantiles;
- outliers and skewed returns;
- sector, country and market-cap concentration;
- currency and benchmark choices;
- transaction-cost and capacity assumptions;
- multiple testing and researcher degrees of freedom;
- data revisions and point-in-time restatements;
- absence of causal identification.

An estimate must be labeled `INSUFFICIENT_DATA` when minimum coverage or sample
rules fail. A result must be labeled exploratory when it was selected after
observing evaluation outcomes. No statistical output may be presented as a
guarantee, recommendation or proof of alpha.

## Conceptual methodological references

The design is informed by established ideas associated with:

- Spearman rank correlation and cross-sectional information coefficients;
- Fama–MacBeth cross-sectional methodology;
- Efron-style bootstrap and bootstrap confidence intervals;
- moving-block and stationary bootstrap methods associated with Politis and
  Romano;
- Newey–West heteroskedasticity/autocorrelation-robust inference;
- Benjamini–Hochberg false-discovery-rate control;
- Holm–Bonferroni family-wise control;
- Westfall–Young resampling and White's Reality Check for data snooping;
- Hansen's Superior Predictive Ability framework;
- chronological holdout and walk-forward validation.

These names identify methodological families to evaluate. They are not claims
that every method is valid for every cohort, nor do they authorize adding a
third-party statistical dependency without a later architecture decision.

## Minimum Wave E statistical gate

Before a factor result is treated as credible, the analysis should demonstrate:

1. canonical cohort identity and explicit exclusions;
2. point-in-time and outcome information barriers;
3. overlapping and non-overlapping views where feasible;
4. cross-sectional IC by date plus pooled diagnostics;
5. horizon/IC-decay analysis;
6. uncertainty intervals with a dependence-aware resampling design;
7. stability or regime analysis;
8. turnover and transaction-cost sensitivity;
9. factor redundancy and interaction diagnostics;
10. chronological validation and at least one untouched out-of-sample test;
11. multiple-testing family and exploratory/confirmatory status;
12. deterministic rerun and complete provenance of every estimate.

Passing this gate validates the research process, not the claim that a factor
will outperform in the future.
