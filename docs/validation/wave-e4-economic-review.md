# Wave E4 adversarial economic review

## Scope

This review attacks the frozen portfolio-construction flow through its public
contracts. It is intentionally independent from the implementation tests and
does not use providers, HTTP, current data, or production changes.

## Tests executed

`tests/integration/test_wave_e4_adversarial.py` covers:

- ticker-keyed trade identity when a middle security is removed;
- deterministic replay under reversed research-result input order;
- zero-turnover and partial-turnover cost arithmetic;
- explicit failure when a fully invested target cannot fund non-zero costs;
- a cash reserve funding costs without leverage or money creation;
- infeasible and unevaluable sector constraints;
- request, ResearchRun, as-of, and ResearchResult identity mismatches;
- SQLite close/reopen persistence with ResearchRun and ResearchResult lineage;
- a network kill switch proving construction does not fall back to providers.

## Economic findings

The tested contracts preserve security identity by forming the union of ticker
keys before calculating deltas. Removing `BBB` cannot shift `CCC` onto `BBB`'s
starting value. Reversed input order produces the same construction result.

Transaction costs are charged on gross traded notional (buys plus sells). A
zero-turnover rebalance has zero cost. A partial rebalance charges only the
changed securities. A fully invested target with a positive cost rate raises an
explicit negative-cash error; the constructor converts that into an
`INFEASIBLE` result with no trades, so it cannot create leverage.

An explicit cash reserve makes the same arithmetic fundable. The result keeps
the pre-cost target weights and records the estimated cost and source lineage;
the reserve is checked to cover the cost.

Sector constraints are not silently guessed: missing sector classification is
reported as `NOT_EVALUATED` and makes the application infeasible. Jointly
impossible sector caps also remain infeasible.

## Defects found

No release-blocking defect was demonstrated in the allowed scope.

One potential integration concern remains documented rather than changed:
`reconcile_target_trades` intentionally requires enough target cash to fund
costs. Callers that construct a fully invested target must specify a cash
reserve or receive an explicit infeasible result. This is economically safe,
but should remain visible in future orchestration UX.

## Scope limitations

This adversarial file does not modify production code and therefore does not
validate provider adapters, live prices, corporate-action execution, or a
future backtest engine. Those require separate contracts and fixtures. SQLite
round-trip coverage here validates the E4 request/result lineage only; it does
not certify every unrelated storage table.

## Quality result

Focused test result: 9 passed.

Ruff is applicable to the Python test file and passes. Ruff does not lint the
Markdown review file (`E902` when passed a `.md` path), so Markdown validation
is documentation review rather than a Ruff target.
