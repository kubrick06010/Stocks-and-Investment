# E4B — Deterministic portfolio constraints

E4B evaluates and applies constraints to ticker-keyed proposed weights. It is
pure: it performs no provider, storage, solver, or current-data access.

Supported constraints are long-only, maximum position weight, minimum cash,
maximum sector weight (requiring an explicit ticker-to-sector map), and maximum
turnover. Missing sector classifications are `NOT_EVALUATED`, and an
application containing such a condition is infeasible rather than silently
relaxed.

Application is deliberately narrow and auditable. A proposal above its
investable budget is proportionally scaled to leave the requested minimum cash.
Position and sector caps then cap violating positions and redistribute their
excess proportionally to eligible ticker-keyed positions. If no eligible
capacity exists, the result is infeasible. Turnover violations are never
repaired by changing the proposal: they remain explicit violations.

Turnover is the gross sum of absolute weight changes over the union of current
and proposed ticker identities. This is distinct from transaction cost and
preserves security identity through missing names.

The result retains the canonical `ConstraintEvaluation` records, including
observed value, limit, status, scope, and rationale. `SATISFIED` and `BINDING`
are feasible; `VIOLATED` and `NOT_EVALUATED` are not.
