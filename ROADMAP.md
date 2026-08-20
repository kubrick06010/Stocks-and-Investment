Stocks-and-Investment — Roadmap

Status

Current project state:

Waves B/C                 VALIDATED
D0.5 Storage              VALIDATED
D1 Thesis                 VALIDATED
D2 History                VALIDATED
D3 Strategy Comparison    VALIDATED
D4 Factor Efficacy        VALIDATED
D5 Watchlists             VALIDATED
D6 Reporting / CLI        VALIDATED
Wave D Integration        VALIDATED
Tests                     481 passed
Skipped                   1 intentional live-provider test
ruff                      PASS
mypy                      PASS
compileall                PASS
git diff --check          PASS
Wave D                    VALIDATED
Wave E                    E0–E6 VALIDATED (E6 is an optional evidence-bound extension)
Wave E.0 Contracts        VALIDATED
Wave E.1 Implementation   VALIDATED
Wave E.2 Contracts        VALIDATED
Wave E.2 Implementation   VALIDATED
Wave E.3 Contracts        VALIDATED
Wave E.3 Implementation   VALIDATED
Wave E.4 Contracts        VALIDATED
Wave E.4 Implementation   VALIDATED
Wave E.5 Contracts        VALIDATED
Wave E.5 Implementation   VALIDATED
Wave E.5 Integration      VALIDATED
Wave E.6 Contracts        VALIDATED
Wave E.6 Implementation   VALIDATED
Wave E Integration        VALIDATED within local, offline V1 scope
Real-data PIT pilot       VALIDATED AS INTEGRATION; ECONOMIC NO-GO
Full economic PIT panel   EXTERNAL DELIVERY REQUESTED

Wave D closure is complete. The P0/P1 sections below remain as the historical
acceptance record and regression checklist for future changes.

⸻

1. Immediate Objective

Close Wave D without adding scope.

The system already has:

* persisted historical research;
* deterministic thesis generation;
* historical change detection;
* strategy comparison;
* persisted backtesting;
* factor efficacy;
* watchlists;
* monitoring;
* reporting;
* CLI access;
* JSON and Markdown serialization.

What remains is proving that these components preserve historical and scientific integrity under adversarial conditions.

Wave D becomes VALIDATED only when the remaining gaps below are closed.

⸻

2. P0 — Complete D4 Cohort Identity

Priority: RELEASE BLOCKER

Current problem:

FactorOutcomeObservation does not carry enough information to guarantee complete universe and benchmark identity.

This prevents D4 from proving that incompatible populations cannot be accidentally aggregated.

Required work

Extend the factor-outcome contract with explicit cohort identity.

Preferred design:

FactorOutcomeObservation
------------------------
ticker
factor_name
factor_version
research_run_id
as_of
factor_score
outcome_horizon
security_return
universe_id / universe_snapshot_id
benchmark_id
benchmark_return
currency
cadence
outcome_status

Alternatively, introduce a stable reference:

information_cohort_id

where the referenced cohort contains:

factor version
universe
date range
horizon
cadence
currency
benchmark

Avoid duplicating both mechanisms unless necessary.

Invariants

Two observations must not silently enter the same efficacy population if they differ in:

factor version
universe
benchmark
horizon
currency convention

Other cohort dimensions should be enforced according to methodology.

Persistence

Update SQLite persistence additively.

Existing Wave B/C/D databases must remain readable.

Add migration tests:

old DB
→ migrate
→ historical data preserved
→ new cohort fields available

Required attacks

Explicitly test:

quality_v1 + quality_v2
SP500 + NASDAQ
3M + 12M
benchmark_A + benchmark_B
EUR + USD where applicable

Expected behavior:

reject

or:

split into explicit independent cohorts

Never silently aggregate.

Exit criteria

[x] cohort identity represented canonically
[x] persistence implemented
[x] migration tested
[x] factor-version mixing blocked
[x] universe mixing blocked
[x] benchmark mixing blocked
[x] horizon mixing blocked
[x] currency mixing blocked where relevant
[x] D4 reports cohort identity
[x] CLI JSON exposes cohort identity

⸻

3. P0 — Complete D3 Fairness Matrix

Priority: RELEASE BLOCKER

D3 now consumes persisted BacktestRun objects and exposes performance correctly.

Remaining task:

prove compatibility detection independently for every relevant assumption.

Required compatibility dimensions

Test individually:

period
historical universe
benchmark
rebalance frequency
selection rule
top_n
weighting method
transaction-cost model
transaction-cost rate
corporate-action policy
return convention
strategy name
strategy version

Required matrix

For each field:

A == B
→ compatible for that dimension
A != B
→ expected mismatch metadata

Tests should alter one variable at a time.

This prevents false confidence from a single fixture containing several simultaneous incompatibilities.

Strategy identity

Explicitly test:

balanced_value_quality_v1
vs
balanced_value_quality_v2

Same family does not mean same strategy identity.

Performance rules

Verify incompatible simulations never produce a misleading direct performance winner.

Agreement/ranking analysis may still be possible where mathematically valid.

Exit criteria

[x] every compatibility field independently tested
[x] mismatch metadata identifies exact field
[x] strategy version isolation tested
[x] gross/net convention tested
[x] benchmark mismatch tested
[x] turnover/cost assumptions tested
[x] incompatible comparison cannot masquerade as valid

⸻

4. P0 — Provider Kill Switch

Priority: RELEASE BLOCKER

Historical research inspection must be completely provider-independent after persistence.

Required scenario

Construct/persist the full historical fixture:

T0
T1
T2
T3

Then:

close database
reopen database
disable every provider
make provider invocation raise immediately

Execute:

thesis
thesis-history
changes
compare-strategies
factor-efficacy
watchlist
report

All must succeed from persisted state.

Kill-switch coverage

Guard against:

HTTP requests
price providers
fundamental providers
universe providers
benchmark downloads
provider refreshes
implicit latest-data fallbacks

A test should fail immediately if any provider path is touched.

Exit criteria

[x] thesis provider-free
[x] history provider-free
[x] D3 provider-free
[x] D4 provider-free
[x] D5 provider-free
[x] D6 provider-free
[x] CLI provider-free
[x] reports provider-free
[x] no current-data fallback exists

⸻

5. P0 — Complete Future-Information Attack Matrix

Priority: RELEASE BLOCKER

The project must prove that later information cannot modify historical interpretation.

T4 attack

After T0–T3 are fully persisted, introduce:

T4 ResearchRun
T4 fundamentals
T4 prices
T4 FactorScores
T4 ThesisSnapshots
T4 outcomes
new universe members

Capture historical objects before and after.

Verify invariance of:

T0 ThesisSnapshot
T1 ThesisSnapshot
T0→T1 ChangeEvents
historical rankings
historical criteria
historical factor scores
historical Watchlist states
old MonitoringEvents
BacktestRun inputs
FactorOutcomeObservation inputs

Extreme outcome attack

Give a historical security an absurd later result:

AAA subsequent return = +500%

Verify it cannot change T0:

classification
drivers
risks
assumptions
invalidators
factor score
ranking
watch state
change materiality

D4 may evaluate the +500%.

Historical research may not consume it.

Exit criteria

[x] T4 attack passes
[x] future filing attack passes
[x] future price attack passes
[x] future universe attack passes
[x] extreme outcome attack passes
[x] D1 unaffected
[x] D2 unaffected
[x] D5 unaffected
[x] D4 alone may consume subsequent outcomes

⸻

6. P0 — Complete Version Isolation Matrix

Priority: RELEASE BLOCKER

Version identity must be preserved throughout the complete system.

Thesis

Test:

structured_thesis_v1
structured_thesis_v2

Historical v1 snapshots remain v1.

CLI/report history must expose the correct version.

No historical regeneration.

Strategy

Test:

balanced_value_quality_v1
balanced_value_quality_v2

ResearchRuns and BacktestRuns remain distinct.

D3 must never merge them.

Factor

Test:

quality_v1
quality_v2

D4 must not aggregate them.

Required invariant

Version is part of identity, not descriptive metadata.

Exit criteria

[x] thesis version isolation
[x] strategy version isolation
[x] factor version isolation
[x] persistence preserves versions
[x] CLI exposes versions where relevant
[x] reports preserve versions
[x] no implicit "latest version" substitution

⸻

7. P0 — Deterministic Rerun Assertions

Priority: RELEASE BLOCKER

Core deterministic behavior exists, but complete D3/D4/D6 rerun coverage is still missing.

Required procedure

Against one unchanged reopened database:

run twice:

StrategyComparator
FactorEfficacyAnalyzer
ResearchReportBuilder
CLI JSON outputs

Compare semantic results.

Expected:

same selections
same compatibility
same metrics
same turnover
same costs
same efficacy cohort
same coverage
same spread
same rank IC
same hit rate
same report structure
same economic JSON payload

Ignore only legitimate nondeterministic fields such as newly generated timestamps/IDs.

Prefer eliminating unnecessary nondeterminism altogether.

Exit criteria

[x] D3 deterministic
[x] D4 deterministic
[x] D6 deterministic
[x] CLI JSON deterministic
[x] reopened DB produces identical results

⸻

8. P1 — Complete CLI Integration Matrix

D6 commands exist, but complete command-path coverage is missing.

Commands

Cover:

stocks thesis
stocks thesis-history
stocks changes
stocks compare-strategies
stocks factor-efficacy
stocks watchlist
stocks report

For every applicable command test

successful request
missing entity
missing historical data
invalid arguments
incompatible data
empty result
JSON
Markdown
human-readable output

Special cases

compare-strategies

Test:

compatible
different universe
different benchmark
different costs
different strategy version
missing BacktestRun

factor-efficacy

Test:

valid cohort
insufficient sample
mixed factor versions
mixed horizon
mixed universe
mixed benchmark
missing outcomes

report

Test:

full history
no watchlist
no outcome
with subsequent outcome
missing ticker

No expected failure should expose a raw traceback.

⸻

9. P1 — Strengthen Report Lineage

Current report lineage should be expanded.

Every major section should expose its evidence origin.

Thesis

ThesisSnapshot
→ ResearchResult
→ ResearchRun

Changes

ResearchChangeEvent
→ from ResearchRun
→ to ResearchRun

Watchlist

WatchlistEntry
→ source ResearchRun
MonitoringEvent
→ triggering ResearchRun

Strategy comparison

StrategyComparison
→ ResearchRuns
→ BacktestRuns

Factor efficacy

FactorEfficacySummary
→ factor version
→ cohort
→ historical FactorScores
→ OutcomeObservations

The report must never become a dead-end presentation object.

⸻

10. P1 — Harden Research / Outcome Separation

Current structural separation exists.

Complete the assertions.

Canonical report structure must distinguish:

RESEARCH AS OF T

from:

SUBSEQUENT OUTCOME

This distinction must survive:

domain representation
text
JSON
Markdown

Required adversarial test

Construct:

T0 thesis = WATCH
later return = +500%

Generate all output formats.

Verify the +500% appears exclusively under subsequent outcome/evaluation.

Search historical research sections and ensure the outcome cannot leak into:

summary
classification
drivers
risks
assumptions
invalidators

⸻

11. P1 — Security Identity Attack

Past project work has already demonstrated the danger of positional alignment.

Attack it everywhere.

Deliberately shuffle ticker ordering between:

T0 ResearchResults
T1 ResearchResults
strategy A rankings
strategy B rankings
factor observations
outcomes

Verify:

D2
D3
D4

remain security-keyed.

No logic should rely on:

zip(list_a, list_b)

without explicit identity alignment.

Add regression tests wherever appropriate.

⸻

12. P1 — Complete Historical Fixture Documentation

The shared four-run fixture is now an important architectural asset.

Document it.

Suggested:

docs/testing/wave-d-historical-fixture.md

Describe:

T0–T3 dates
AAA story
BBB story
CCC value-trap story
DDD deterioration story
EEE role
strategy disagreement
watch conditions
factor outcomes
future-data attacks
expected structural behavior

Do not document fixture values as investment truths.

It is a correctness model.

⸻

13. P1 — Complete Manual Audit

After automated closure, manually reconstruct the histories.

AAA

Answer:

What did the system know at T0?
Why was AAA WATCH?
What changed at T1?
What changed at T2?
Why did Graham flip?
When did the watch condition trigger?
What was the subsequent outcome?
Was that outcome absent from historical thesis generation?
Which thesis/factor/strategy versions were involved?
Which ResearchRun produced every state?

DDD

Answer:

When did deterioration first become visible?
Which metrics changed?
Which factors changed?
When did classification change?
Could T3 deterioration contaminate T0/T1?

Strategies

Answer:

Where do Graham and Balanced disagree?
Are BacktestRuns comparable?
Gross result?
Net result?
Turnover?
Transaction costs?
Benchmark?

Quality factor

Answer:

Which observations entered?
Factor version?
Universe?
Benchmark?
Horizon?
Eligible?
Usable?
Excluded?
Coverage?
Spread?
Rank IC?
Hit rate?

⸻

14. Wave D Final Closure Gate

After P0/P1 completion run:

ruff check src tests
mypy src
python3 -m pytest -q -p no:cacheprovider
python3 -m compileall -q src
git diff --check

Also run focused suites for:

D3 fairness
D4 cohort identity
D6 CLI
provider kill switch
future-data attacks
version isolation
security ordering
determinism
report information barrier
Wave D E2E

Then inspect:

git diff --stat
git diff

Look specifically for:

Wave E code
provider access
duplicate financial formulas
positional alignment
silent fallbacks
hard-coded production fixture behavior
unnecessary schema churn

⸻

15. Wave D Acceptance Criteria

Only declare:

D0.5 Storage             VALIDATED
D1 Thesis                VALIDATED
D2 History               VALIDATED
D3 Strategy Comparison   VALIDATED
D4 Factor Efficacy       VALIDATED
D5 Watchlists            VALIDATED
D6 Reporting / CLI       VALIDATED
Wave D Integration       VALIDATED

when all of the following hold:

[x] D4 cohort identity complete
[x] D3 fairness matrix complete
[x] provider kill switch passes
[x] T4 attack passes
[x] extreme outcome attack passes
[x] thesis version isolation passes
[x] strategy version isolation passes
[x] factor version isolation passes
[x] horizon mixing blocked
[x] universe mixing blocked
[x] benchmark mixing blocked
[x] security-order attack passes
[x] D3 deterministic rerun
[x] D4 deterministic rerun
[x] D6 deterministic rerun
[x] CLI integration matrix passes
[x] report lineage complete
[x] research/outcome separation explicit
[x] DB close/reopen passes
[x] no provider calls after reopen
[x] full test suite green
[x] ruff green
[x] mypy green
[x] compileall green
[x] git diff --check green

No partial credit.

If one release blocker remains:

Wave D = VALIDATED
Wave E = VALIDATED through E6 within the documented local/offline V1 scope

⸻

16. Wave E — Completed Direction

Wave D was validated before opening Wave E. The sequence below is now the
completed execution record for the current V1 scope.

Executed priority:

E1 Advanced Statistical Validation
E2 Qualitative Filings Intelligence
E3 Research Automation
E4 Advanced Portfolio Construction
E5 Interactive Research Interface
E6 Optional LLM Narrative Layer

E6 is intentionally an evidence-bound optional narrative extension; it does
not add an LLM dependency or external inference service.

⸻

17. E1 — Advanced Statistical Validation

This is currently the recommended next major wave.

Wave D can calculate factor efficacy.

Wave E should determine whether apparent efficacy is credible.

E1.1 Larger historical samples

Move beyond tiny synthetic fixtures.

Build reproducible historical research datasets with sufficient cross-sectional and longitudinal coverage.

Preserve:

point-in-time fundamentals
historical universe membership
delisting where possible
factor versions
benchmark identity
corporate actions

Execution checkpoint (2026-08-20): an exact Kaggle v3 CC BY artifact was
acquired and run through the E1 pipeline. It produced 638 factor-outcome rows
across 28 dates and passed hash, PIT, persistence and close/reopen controls.
Because the public sample contains only 99 price histories and 17 raw
fundamental histories, independent review and uncertainty results keep the
economic verdict at `NO-GO`. Full-panel access is requested at
https://github.com/Finance-broski/pit-data-sample/issues/1. No alpha claim is
authorized until the full licensed panel passes ADR-011.

E1.2 Non-overlapping cohorts

12M forward returns sampled monthly overlap heavily.

Add methodologies for non-overlapping evaluation.

Compare:

monthly overlapping observations
quarterly cohorts
annual cohorts

Do not treat overlapping observations as independent.

E1.3 Confidence intervals

Add robust uncertainty estimation.

Candidates:

bootstrap confidence intervals
block bootstrap where temporal dependence matters

Do not make significance claims before methodology is explicit.

E1.4 Factor stability through time

Evaluate factors by:

year
market regime
volatility regime
valuation regime

Ask:

Is Quality useful consistently, or is aggregate efficacy hiding unstable periods?

E1.5 Cross-sectional IC

Calculate factor IC per research date.

Then analyze:

mean IC
median IC
IC volatility
IC hit rate
IC decay

This is preferable to relying only on one pooled correlation.

E1.6 IC decay

Measure predictive association across:

1M
3M
6M
12M
24M

where valid.

Ask how quickly signal decays.

E1.7 Turnover-adjusted efficacy

A factor may predict returns while causing excessive portfolio turnover.

Evaluate:

signal
vs
turnover
vs
transaction costs

E1.8 Multiple-testing control

As the factor library grows, false discoveries become increasingly likely.

Design support for:

multiple hypothesis testing
false discovery rate
family-wise error considerations

Do not p-hack the factor library.

E1.9 Factor correlation / redundancy

Measure:

Value ↔ Graham
Quality ↔ Profitability
Momentum ↔ Trend
Composite ↔ components

Identify redundant signals.

E1.10 Factor interactions

Investigate combinations such as:

Value × Quality
Value × Financial Health
Quality × Momentum

without automatically optimizing weights.

E1.11 Out-of-sample validation

Introduce explicit:

development period
validation period
out-of-sample period

Do not tune and evaluate on the same history.

E1.12 Walk-forward validation

Eventually support:

train/define methodology
→ freeze
→ evaluate next period
→ advance

without rewriting past methodology.

⸻

18. E2 — Qualitative Filings Intelligence

Only after quantitative integrity is stronger.

Potential sources:

annual reports
quarterly reports
regulatory filings
earnings releases
earnings calls

Potential capabilities:

business-model extraction
risk-factor changes
management guidance
capital-allocation analysis
competitive positioning
accounting-policy changes
material-event detection

Every extracted claim must preserve source lineage.

LLMs may assist later, but raw qualitative evidence must remain inspectable.

⸻

19. E3 — Research Automation

Once historical research and validation are trustworthy:

new filing
→ new observations
→ ResearchRun
→ thesis
→ changes
→ watchlist evaluation
→ report

Potential automation:

scheduled research runs
new-filing detection
watchlist reevaluation
material-change reports
factor research refresh

Automation must use the same deterministic pipeline.

No hidden parallel research engine.

⸻

20. E4 — Advanced Portfolio Construction

Only after signal credibility is better understood.

Potential work:

factor-aware weighting
risk constraints
position limits
sector constraints
turnover penalties
transaction-cost-aware construction
volatility targeting
risk contribution

Do not jump immediately to mean-variance optimization.

Portfolio construction should consume validated research signals rather than manufacture them.

⸻

21. E5 — Interactive Research Interface

The current CLI/report architecture should remain the source of analytical truth.

A future UI may expose:

stock research
thesis timeline
factor history
strategy comparison
watchlists
backtests
factor efficacy
source lineage

The UI must consume existing services.

Do not duplicate financial logic in frontend code.

⸻

22. E6 — Optional LLM Narrative Layer

LLM functionality remains optional and downstream.

Correct architecture:

persisted evidence
        ↓
structured deterministic analysis
        ↓
structured thesis/report
        ↓
optional LLM narrative renderer

Incorrect architecture:

raw financial data
        ↓
LLM
        ↓
investment truth

An LLM must never become the canonical source of:

factor values
classification
historical state
returns
ranking
watch triggers

Possible future use:

narrative synthesis
filing summarization
question answering over evidence
research-report explanation
change summaries

with citations/source references.

⸻

23. Long-Term Scientific Principle

The project should preserve four distinct layers:

EVIDENCE
    ↓
RESEARCH INTERPRETATION
    ↓
SUBSEQUENT OUTCOME
    ↓
POST-HOC EVALUATION

Never collapse them.

The past must remain immutable.

The future may evaluate the past.

The future may not rewrite what the past knew.

⸻

24. Identity Invariants

Every future feature must preserve the identities that Waves B–D established.

Security

Which company/security?

Date

When was the information available?

Universe

Which investable population existed then?

ResearchRun

Which historical decision generated this state?

Strategy

Which methodology and version?

Factor

Which factor and version?

Thesis

Which thesis methodology version?

Benchmark

Relative to what?

Outcome horizon

What future period is being evaluated?

Money

Do portfolio wealth, turnover and costs reconcile?

If any of these identities are lost, the analytical result must be considered suspect.

⸻

25. Definition of Done

The long-term goal is not merely a stock screener.

The system should eventually be capable of reconstructing:

WHAT DID WE KNOW?
        ↓
WHAT DID WE THINK?
        ↓
WHY?
        ↓
WHAT CHANGED?
        ↓
WHEN?
        ↓
WHAT DID WE DO WITH THAT INFORMATION?
        ↓
WHAT HAPPENED AFTERWARD?
        ↓
WHICH SIGNALS ACTUALLY WORKED?
        ↓
HOW CERTAIN ARE WE?

Every answer must be:

point-in-time
versioned
reproducible
traceable
auditable
economically coherent
scientifically honest

⸻

Historical Execution Order (completed)

The following gates were executed and closed:

1. D4 cohort identity
2. D3 fairness attack matrix
3. provider kill switch
4. T4/future-information attacks
5. version-isolation matrix
6. deterministic reruns
7. CLI integration matrix
8. report lineage + outcome separation
9. security-order attack
10. full Wave D closure gate

All ten gates passed before Wave D was marked VALIDATED. Wave E0–E6 then
completed with additive contracts, provider-free historical inspection and
the quality gates recorded above. Future expansion beyond E6 requires a new
architecture decision and is not silently implied by this roadmap.
