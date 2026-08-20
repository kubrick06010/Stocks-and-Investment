# E4 — Advanced Portfolio Construction Research

Status: research only. No production implementation is proposed by this document.

## Purpose and scope

Portfolio construction is the boundary between a persisted research decision and
the positions simulated or held. It must consume validated, versioned signals;
it must not create a new source of financial or investment meaning.

The current repository already has the right first boundary:

```text
ResearchResult / CompositeScore
        ↓ persisted selection and rank
portfolio construction
        ↓ security-keyed target weights
Backtest / portfolio accounting
        ↓ prices, transactions, costs, returns
outcomes
```

The current V1 backtest forms an equal-weight top-N portfolio, preserves ticker
identity in mappings, and charges transaction costs on gross traded notional.
`BacktestConfigV1` rejects weighting methods other than `equal_weight`. E4
should extend this boundary deliberately, without moving metric calculations,
strategy evaluation, or provider access into the constructor.

This document evaluates practical construction families and recommends a small,
deterministic next step. It does not recommend a live-trading policy or personal
investment allocation.

## Signal-to-weight boundary

The boundary should have two explicit stages:

1. **Signal eligibility and selection.** A strategy consumes point-in-time
   `ResearchResult`, `FactorScore`, `CriterionResult`, and universe artifacts.
   It emits an immutable selection decision with strategy name/version,
   information set, missing-data policy, and security identity.
2. **Weight construction.** A portfolio constructor consumes that decision,
   current portfolio state, prices available at the rebalance date, and an
   explicitly versioned construction policy. It emits target weights or an
   explicit infeasibility result.

The constructor must not:

- fetch data or calculate financial metrics;
- rerun a historical strategy;
- turn an unavailable score into zero;
- infer a sector, risk, or price constraint from an absent field;
- silently drop a ticker while retaining a positional weight;
- use future prices or outcomes;
- compare securities across currencies without an explicit policy.

Every target weight should be keyed by ticker, with a complete construction
record containing:

- source ResearchRun and strategy/version;
- source rank/score and factor components, where used;
- eligible universe snapshot;
- construction method/version;
- input portfolio state and valuation date;
- excluded securities and reasons;
- constraints and their units;
- turnover and transaction-cost assumptions;
- status: feasible, insufficient-data, or infeasible.

This keeps the research interpretation separate from the mechanical question of
how much capital to assign.

## Candidate weighting methods

### Equal weight

For a selected set of `N` securities, each receives `1/N`. It is transparent,
robust to score scale, and a useful control portfolio. Its weaknesses are that
it ignores conviction, volatility, correlation, liquidity, and concentration
created by unequal underlying risks. It can also create avoidable turnover when
membership changes.

Equal weight remains the reference against which more complex constructors
should be compared.

### Score-proportional weight

For non-negative normalized scores, a basic rule is:

```text
w_i = score_i / Σ score_j
```

This is easy to explain but often overreacts to small score differences and
confuses ordinal ranking with calibrated expected return. A score of 80 is not
necessarily twice as attractive as a score of 40. It is only defensible when
the score scale, missing-data policy, clipping, and version are fixed and
documented.

A safer variant is a bounded transform of rank or score, followed by a cap and
normalization. The transform itself must be versioned and must not be tuned on
the evaluation period.

### Conviction buckets

Map ranks or score bands to a small number of weights, for example high/medium/
low conviction, then cap each position. This reduces sensitivity to noise while
preserving some differentiation. Boundary effects and ties must be deterministic
and resolved by ticker identity, not input order.

### Volatility-aware weighting

Inverse-volatility weighting assigns less capital to securities with higher
estimated volatility:

```text
w_i ∝ 1 / volatility_i
```

The estimate needs an as-of window, price adjustment policy, minimum history,
missing-data behavior, and a cap. It can reduce standalone volatility but does
not account for correlation; concentrated names can still dominate total risk.
It also makes construction sensitive to stale or discontinuous prices.

### Risk-parity / equal risk contribution

Risk contribution attempts to make each position contribute a similar share of
portfolio volatility. For covariance matrix `Σ`, portfolio volatility is

```text
σ_p = sqrt(wᵀΣw)
```

and the marginal contribution of asset `i` is `(Σw)_i`; its total risk
contribution is `w_i(Σw)_i / σ_p`. Equal-risk-contribution construction seeks
similar contributions subject to constraints.

This uses more data and a covariance estimate that can be unstable for small
samples, regime changes, and highly correlated securities. It is not a natural
replacement for a weak research signal: risk balancing can allocate meaningfully
to a fundamentally unattractive security unless eligibility is enforced first.

### Mean-variance and Black-Litterman-style construction

Mean-variance optimization is highly sensitive to expected-return and
covariance estimation error. Black-Litterman-style models can regularize views
relative to a prior, but introduce additional assumptions and calibration
choices. Neither is appropriate as the repository's first advanced constructor:
the current research layer has not established stable expected-return estimates,
large covariance samples, or a validated view-calibration process.

These methods remain research candidates, not V1 defaults.

## Constraints

Constraints should be explicit, typed, and evaluated before execution or
simulation. At minimum, future construction should support:

- long-only: `w_i >= 0`;
- fully invested or explicit cash residual: `Σw_i <= 1`;
- maximum position weight;
- minimum position weight, only when it does not force unwanted holdings;
- maximum number of holdings;
- minimum score/eligibility threshold;
- sector or industry caps when classifications are available and point-in-time;
- country/currency exposure limits where supported;
- turnover cap;
- liquidity or minimum-price filters, if sourced and versioned;
- existing-position hold/liquidation rules;
- cash reserve and minimum trade size.

Constraints are not interchangeable. A sector cap needs a dated classification
source; it must not be inferred from a current classification in a historical
simulation. A turnover cap must use the same security-keyed pre-trade values as
the cost model. A minimum trade size can leave residual cash and must not be
reported as fully invested.

The constructor must distinguish:

- **ineligible input**: the security cannot enter the candidate set;
- **constraint exclusion**: it was eligible but excluded by a limit;
- **infeasible problem**: no target portfolio satisfies all constraints;
- **insufficient data**: required input is unavailable;
- **valid cash residual**: a feasible portfolio deliberately leaves cash.

## Turnover and transaction-cost penalties

Turnover and cost are separate concepts. The current C6 convention counts buys
plus sells as gross traded notional and reports traded notional divided by
pre-trade portfolio value. E4 should retain that convention for continuity,
while also permitting a named alternative such as half absolute weight change.
The convention belongs in the persisted construction/backtest configuration.

For target weights `w*` and pre-trade security values `V_i`, a simple traded
notional approximation is:

```text
traded_notional = Σ |V_i* - V_i|
transaction_cost = traded_notional × cost_rate
```

where the union of current and target tickers is used. This is only a valid
approximation when the trade execution model, price convention, and cash
handling are explicit. It must not be applied to a filtered list whose symbols
can shift.

There are three useful ways to control turnover:

1. hard turnover cap: reject or reduce a target that exceeds the cap;
2. no-trade bands: retain a position until its desired weight differs by a
   specified band;
3. cost-aware objective: penalize turnover during construction.

For a score-based objective, a conceptual penalty is:

```text
objective = signal_utility(weights) - λ × traded_notional
```

This must not be mistaken for an economic expected-return model. `λ` needs units,
cost calibration, versioning, and out-of-sample validation. A hard cap is easier
to explain and reject when infeasible; a penalty may produce less turnover but
can hide a tradeoff unless the unpenalized signal and cost are both reported.

## Volatility targeting

Volatility targeting scales a portfolio or sleeve toward a target annualized
volatility:

```text
scale = target_volatility / estimated_portfolio_volatility
```

The scale should be bounded and applied to an explicit risky sleeve plus cash or
financing policy. It requires a historical lookback, return frequency,
annualization convention, minimum observations, adjustment policy, and a
leverage prohibition or cap. If volatility is missing or zero, the result must
be `INSUFFICIENT_DATA` or a documented unscaled fallback; it must not silently
create leverage. Volatility targeting changes exposure over time and can add
turnover precisely when volatility rises, so its net effect must be measured
after costs.

It should initially be an optional overlay for a fully formed portfolio, not a
replacement for signal selection.

## Risk contribution

Risk contribution is useful for explaining why equal capital does not imply
equal risk. A future constructor may report, without optimizing, each holding's
weight, marginal contribution, total contribution, and contribution share.

Required safeguards include:

- positive-semidefinite covariance input or an explicit repair/version;
- sufficient overlapping return history;
- date-keyed alignment;
- stable treatment of missing observations;
- explicit handling of a zero-volatility or singular covariance matrix;
- deterministic solver tolerances and iteration limits;
- position and leverage constraints;
- a complete infeasibility result rather than a best-effort silent answer.

Risk contribution should first be an explanatory diagnostic and acceptance test.
It should not automatically override a validated fundamental/technical
eligibility decision.

## Infeasibility and failure semantics

Portfolio construction must fail honestly. A constructor should return a typed
result with status, diagnostics, and any safe partial information rather than
silently relaxing a constraint.

Examples:

- selected securities are missing as-of prices;
- all eligible securities violate a minimum score or liquidity rule;
- maximum position caps cannot absorb the required investment;
- sector caps make the requested top-N impossible;
- turnover cap permits no path from the current portfolio;
- covariance has insufficient history or invalid units;
- costs exceed available capital;
- target weights do not sum to the declared investment budget;
- mixed currencies have no conversion policy.

Relaxations, if ever supported, must be ordered and versioned, for example:
first leave cash, then reduce the requested number of holdings, otherwise return
infeasible. The selected relaxation must be persisted. V1 should not have an
implicit relaxation ladder.

## Recommended deterministic V1

### Recommendation

Keep `equal_weight` as the control and introduce one narrowly scoped optional
constructor later:

```text
validated persisted selection
→ top-N by rank
→ long-only equal weight
→ maximum position cap
→ optional explicit cash residual
→ security-keyed turnover/cost calculation
→ typed feasible/infeasible result
```

The initial policy should support only:

- top-N selection from persisted rank;
- equal weight among selected securities;
- long-only weights;
- maximum position cap when it is mathematically compatible;
- no leverage or shorting;
- explicit base currency and price-adjustment policy;
- current C6 gross-notional turnover convention;
- explicit transaction-cost rate;
- deterministic ticker tie-breaks;
- no-trade or optimization heuristics.

If a cap conflicts with the equal-weight target, V1 should return
`INFEASIBLE` rather than secretly redistribute weights. A later, separately
versioned `equal_weight_capped_v2` may define a redistribution algorithm.

### Why this is the correct next step

It preserves a strong control, makes every decision inspectable, and lets future
weighting methods be evaluated against the same persisted selections, prices,
universe snapshots, turnover convention, and benchmark. It also avoids claiming
that a score is a calibrated expected return or that a risk model has predictive
content that has not been validated.

### Explicitly deferred methods

Defer score-proportional, inverse-volatility, risk-parity, volatility targeting,
sector-aware construction, and turnover-penalized optimization until each has:

- a frozen domain/interface contract;
- point-in-time inputs and provenance;
- an independent hand-calculation fixture;
- infeasibility and missing-data tests;
- gross/net and turnover attribution;
- out-of-sample comparison against equal-weight;
- versioned persistence and close/reopen tests.

## Non-goals

E4 does not include:

- strategy optimization or weight tuning against the full history;
- mean-variance, Black-Litterman, or machine-learning allocation;
- broker execution, order routing, or live trading;
- leverage, shorting, derivatives, or margin;
- hidden current-data refreshes;
- replacing factor scores with portfolio weights;
- changing the validated C6 return or corporate-action semantics;
- treating a higher backtest return as proof that a constructor is superior;
- adding a dashboard or LLM narrative layer.

## Evaluation plan for a future implementation

Every constructor should be compared on the same persisted research decisions,
historical universes, dates, benchmark, price policy, and transaction-cost model.
The evaluation should report:

- selection identity and eligibility coverage;
- target weights and cash residual;
- realized turnover and traded notional;
- gross and net return;
- transaction costs;
- volatility, drawdown, and exposure;
- concentration and risk contribution where relevant;
- constraint binding and infeasibility counts;
- reproducibility after database reopen;
- out-of-sample results and sensitivity to reasonable parameter changes.

The comparison must preserve the distinction between a better construction
mechanically and a better underlying signal. A weighting method cannot repair a
weak or biased research signal; it can only change the portfolio consequences of
that signal.

## Methodology references

The following established works are useful conceptual anchors for later
implementation review; they are not dependencies or an endorsement of any
strategy:

- Markowitz (1952), *Portfolio Selection* — mean-variance framing and its
  estimation sensitivity.
- Black and Litterman (1992), *Global Portfolio Optimization* — combining a
  market-equilibrium prior with explicit views.
- Maillard, Roncalli, and Teïletche (2010), *The Properties of Equally Weighted
  Risk Contribution Portfolios* — risk-contribution construction.
- Moreira and Muir (2017), *Volatility-Managed Portfolios* — motivation for
  volatility-managed exposure and the need to test implementation assumptions.

These references do not remove the repository's requirements for point-in-time
data, versioned methodology, explicit costs, and independent validation.

## Final recommendation

E4 should begin with a contract and test freeze around a deterministic,
long-only, top-N equal-weight constructor with explicit caps, cash, turnover,
cost, provenance, and infeasibility semantics. Treat it as a controlled
extension of C6, not as an optimizer. Only after that control is reproduced and
validated should more sophisticated weighting or risk-aware methods be
considered.
