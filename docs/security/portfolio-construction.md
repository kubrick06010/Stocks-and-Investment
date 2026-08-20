# E4 — Threat and Scientific-Integrity Review

## Scope and V1 security posture

This review covers advanced portfolio construction built on persisted, versioned
research artifacts. It does not authorize production implementation. The V1
recommendation is a deterministic, offline-capable construction layer with
explicit constraints, an injected clock, immutable inputs, and a transparent
fallback to an unoptimized feasible portfolio. No broker, live-trading, daemon,
or arbitrary external solver should be required.

Portfolio construction must consume validated `FactorScore`, `ResearchResult`,
`UniverseSnapshot`, price, currency, and cost observations. It must not create
signals, re-run historical research, or fetch current data as a fallback.

## Threat and integrity review

### Leverage and negative cash

Unconstrained target weights, rounding, fees, short positions, and stale prices
can create leverage or negative cash without an obvious exception. A solver may
also return a mathematically feasible answer that violates the economic account
model after trading costs.

Required controls:

- represent long, short, gross exposure, net exposure, borrowing and cash as
  separate quantities;
- make leverage, shorting, and borrowing explicit opt-in capabilities;
- enforce post-trade cash and exposure constraints, not only pre-trade targets;
- reject a portfolio with negative cash unless an explicit borrowing policy and
  financing rate exist;
- include fees, taxes, slippage and minimum trade effects before feasibility is
  assessed;
- persist pre-trade state, target state, trades, post-trade state and all
  constraint residuals.

V1 limit: long-only, fully funded, no leverage, no shorting, no margin and no
portfolio construction that relies on implicit borrowing.

### Concentration and correlated exposure

Security, sector, industry, country, currency and factor concentration can be
hidden by nominal position limits. Correlated names can create a concentrated
economic bet even when each individual weight passes.

Required controls:

- explicit per-security, sector, industry, country and currency limits;
- a declared treatment for unknown classifications: reject, cap, or place in an
  `UNKNOWN` bucket; never silently drop them;
- report gross and net concentration separately;
- preserve the universe and classification snapshot used to construct the
  portfolio;
- distinguish hard constraints from diagnostic warnings;
- report effective number of positions and factor exposure where available.

V1 limit: support security and explicitly sourced sector limits first; do not
pretend that missing classifications are diversified.

### Stale, missing, and non-comparable prices

Stale prices can make a portfolio appear feasible and cheap while hiding an
untradeable or materially changed position. Missing prices must not be replaced
with zero, the last current quote, or an unrelated ticker's value.

Required controls:

- require an as-of price with source, currency, adjustment policy, timestamp and
  staleness age;
- define a maximum age by instrument/universe policy;
- reject or mark `INSUFFICIENT_DATA` when a required price is absent or stale;
- preserve ticker identity in keyed records throughout valuation and trade
  generation;
- disallow mixing raw, split-adjusted and total-return-adjusted prices in one
  economic calculation unless the policy explicitly supports it;
- make market-closed dates and holiday handling deterministic.

V1 limit: no optimizer may infer prices. A caller must supply a complete,
validated price view or receive an explicit failure.

### FX and base-currency risk

Cross-currency construction can silently violate weights, cash constraints and
returns if conversion dates or rates differ. A portfolio value in USD cannot be
compared directly with a EUR price.

Required controls:

- require portfolio base currency and instrument currency on every value;
- require an FX observation with its own as-of date, source, units and
  availability timestamp;
- define whether FX is fixed at trade time, valued at each rebalance, or both;
- reject missing or stale FX rather than treating it as one or zero;
- preserve FX conversion in attribution and provenance;
- test currency mismatch and cross-currency rounding independently.

V1 limit: one base currency per construction run, explicit FX inputs only, no
automatic currency conversion through a provider hidden inside the constructor.

### Missing covariance and unstable risk estimates

Risk-aware weighting can fail when covariance history is short, non-overlapping,
singular, mismatched by date, or contaminated by future observations. A matrix
may be numerically positive semidefinite while economically meaningless.

Required controls:

- align return series by date and ticker identity, never by positional order;
- record lookback window, minimum observations, missing-data policy and return
  convention;
- validate symmetry, finite values, dimensions and positive semidefiniteness;
- detect singularity and ill-conditioning before solving;
- make shrinkage, winsorization and regularization explicit methodology versions;
- reject insufficient covariance data instead of silently using an identity
  matrix;
- include covariance inputs or stable references in the construction lineage.

V1 limit: no covariance optimizer is required. If risk constraints are used,
prefer bounded volatility or deterministic diagonal risk inputs until a validated
covariance methodology exists.

### Solver nondeterminism and reproducibility

Different BLAS versions, solver tolerances, thread counts, random seeds and
tie-breaking rules can produce different weights from identical research data.
This makes a historical portfolio impossible to explain.

Required controls:

- persist solver name/version, objective version, constraints, tolerances,
  random seed, numerical precision and environment metadata;
- provide deterministic tie-breaking by stable security identifier;
- use fixed solver settings and single-threaded mode where required for V1;
- verify returned solutions against constraints independently of solver status;
- distinguish `OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `NUMERICAL_FAILURE` and
  `INSUFFICIENT_DATA`;
- never accept a solver's success flag without checking residuals and cash
  reconciliation;
- make rerunning the same immutable inputs produce the same economic result.

V1 limit: prefer a deterministic projection/greedy constructor for simple
constraints. External optimization is optional and must not be the source of
truth for signals or accounting.

### Infeasible constraints

Conflicting position, sector, turnover, cash, minimum trade and volatility
constraints can make a problem infeasible. Automatically relaxing constraints
can create an unrecorded strategy change.

Required controls:

- classify constraints as hard or soft before execution;
- return an infeasibility certificate naming the conflicting constraints where
  possible;
- never relax a hard constraint implicitly;
- if soft constraints are permitted, persist penalty weights, relaxation order
  and final violations;
- provide a deterministic preflight feasibility check;
- fail closed when no permissible portfolio exists.

V1 limit: no silent constraint relaxation and no automatic leverage rescue.

### Turnover and transaction-cost manipulation

An optimizer can improve a backtest by ignoring turnover, choosing a favorable
cost interpretation, or repeatedly trading tiny positions. Comparing gross
returns with net returns is another common integrity failure.

Required controls:

- define turnover from actual pre-trade holdings and target holdings keyed by
  security;
- define whether traded notional includes both buys and sells;
- calculate costs from traded notional using a versioned cost model;
- include minimum commissions, spread/slippage and taxes where applicable;
- preserve gross return, net return, turnover and costs as separate fields;
- apply the same cost model to construction, backtest and comparison;
- test zero turnover, partial turnover, full liquidation and tiny-trade cases;
- prohibit target weights that are achieved only by negative cash.

V1 limit: explicit traded-notional cost model, no cost-free rebalancing and no
post-hoc cost adjustment to improve performance.

### Signal leakage and current-data fallback

Construction can leak future information through current factor scores, current
universe membership, revised statements, future prices, outcome observations,
or a provider call made when a historical input is absent.

Required controls:

- accept a frozen `as_of` and `BacktestDataView`/equivalent information set;
- require every signal and classification to be available by the construction
  timestamp;
- reject future filing, price, universe and outcome observations;
- do not fill missing historical values from latest data;
- persist research-run IDs, strategy/factor versions and universe snapshot IDs;
- keep future `OutcomeObservation` data outside the construction input type;
- add a provider kill-switch test after database reopen;
- attack the pipeline by inserting future data physically into storage before
  constructing the portfolio and assert unchanged historical output.

V1 limit: construction consumes persisted research decisions; it never invokes
providers or recomputes historical signals.

### Versioning and audit lineage

Changing a weighting rule, constraint, cost model, risk model, adjustment policy
or solver setting can change historical portfolios. Reusing a strategy name while
silently changing its version destroys comparability.

Persist at minimum:

- construction method and version;
- strategy and factor names plus versions;
- source ResearchRun IDs and exact selected ResearchResult IDs;
- universe name, version and as-of date;
- price/FX snapshot IDs and adjustment policies;
- base currency and return convention;
- constraints and missing-data policy;
- weighting method and top-N/selection rule;
- cost and slippage model/version;
- risk/covariance methodology/version;
- solver identity/settings or deterministic algorithm identity;
- code/data snapshot and creation timestamp.

Historical construction records must be immutable. A newer methodology creates a
new version; it does not rewrite prior weights or outcomes.

### Numerical stability

Floating-point cancellation, near-zero denominators, rounding, overflow and
ill-conditioned matrices can produce apparently valid but economically invalid
weights.

Required controls:

- use finite-value validation at every boundary;
- define tolerances and decimal/float conventions explicitly;
- validate weights sum to the permitted total within tolerance;
- reconcile cash, holdings, prices, FX and costs independently;
- reject NaN, infinity, negative quantities in long-only mode and unexplained
  residuals;
- test extreme prices, tiny weights, large notionals, zero portfolio value and
  nearly singular covariance;
- use stable algorithms and bounded iterations; never accept non-convergence as
  success.

### Unsafe external solvers and execution boundaries

External solvers may execute native code, load arbitrary files, consume
unbounded resources, or return untrusted output. A solver must not be able to
fetch data or mutate the research store.

Required controls:

- keep solver integration behind a narrow injected interface;
- pin and audit dependencies; avoid unreviewed binary solver downloads;
- restrict filesystem, network and subprocess access where deployment permits;
- set time, memory and iteration limits;
- validate solver output against an independent domain validator;
- treat solver output as a proposal, never as authority over accounting or
  provenance;
- record failures and input/output hashes without serializing unsafe objects;
- never deserialize arbitrary solver state or pickle payloads.

V1 limit: no network-enabled solver, no arbitrary code execution, no untrusted
serialized optimization model, and no solver required for the baseline path.

## Recommended adversarial test matrix

At minimum, add deterministic tests for:

- long-only fully funded construction with exact cash reconciliation;
- attempted leverage, shorting and negative cash rejection;
- security, sector and unknown-sector concentration limits;
- missing/stale price and mismatched price-adjustment policy;
- cross-currency price without FX, stale FX and currency mismatch;
- covariance dates reordered, missing, too short, asymmetric, singular and
  non-finite;
- identical inputs rerun with identical weights and economic outputs;
- infeasible hard constraints and explicit soft-constraint relaxation;
- zero, partial and high-turnover rebalance with hand-calculated costs;
- future filing, price, universe, outcome and current-data provider kill switch;
- strategy/factor/construction/cost/risk/solver version separation;
- altered input order preserving ticker-keyed results;
- NaN, infinity, overflow, zero capital and near-zero denominators;
- solver timeout, malformed output, constraint residual failure and unsafe
  serialized payload rejection;
- close/reopen persistence of weights, trades, constraints, costs and lineage.

Each test should state whether it proves a safety invariant, a financial identity,
or only a deterministic implementation property. Passing tests do not establish
that a strategy has economic merit.

## V1 scope and release recommendation

Release V1 only with:

- long-only, fully funded portfolios;
- deterministic equal-weight or bounded signal-weight construction;
- explicit security/sector limits;
- explicit base currency and validated FX inputs;
- persisted ResearchRun/ResearchResult lineage;
- actual turnover and traded-notional costs;
- no hidden provider access or future outcome inputs;
- independent post-construction validation and close/reopen reproducibility;
- transparent failure when data or constraints are insufficient.

Defer leverage, shorting, margin, tax-lot optimization, derivatives, intraday
execution, stochastic optimization, automatic constraint relaxation, live
brokers and portfolio optimization tuned on the same data used for evaluation.

The principal security and scientific-integrity decision is to make a feasible,
auditable, deterministic portfolio more valuable than a higher-scoring but
unreproducible optimizer. Portfolio construction must remain downstream of
validated research and must never manufacture evidence, rewrite history, or hide
economic assumptions behind solver output.
