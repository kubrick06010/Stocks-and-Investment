# Wave E4 portfolio-construction contracts

Wave E4 converts persisted, versioned `ResearchResult` selections into an
inspectable target portfolio. It does not create signals, alter rankings or
mutate the accounting ledger.

`PortfolioConstructionRequest` freezes the research run/result identity,
capital, currency, current weights and policy version. A policy freezes the
weighting method, constraints and transaction-cost convention. The result
retains ticker-keyed target positions, trade deltas, costs, constraint
evaluations and source lineage.

V1 supports deterministic equal and score-proportional weighting. It fails
explicitly when caps/cash/turnover constraints are infeasible. Risk-model,
covariance and optimizer semantics are deferred rather than approximated.
