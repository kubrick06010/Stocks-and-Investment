# Portfolio-construction reporting

`portfolio_construction.py` is a read-only presentation adapter for the
validated portfolio-construction contracts. It consumes a
`PortfolioConstructionRequest`, `PortfolioConstructionPolicy`, and
`PortfolioConstructionResult`, then builds the canonical `ResearchReport`.

The report preserves:

- target positions and cash weight;
- policy constraints and their evaluations;
- security-keyed trade estimates;
- gross traded notional, turnover, cost model, rate, and estimated cost;
- request, policy, result, research-run, and source-observation lineage;
- explicit `valid`, `infeasible`, or `insufficient_data` status.

The adapter performs no portfolio arithmetic, provider access, persistence, or
fallback to current data. JSON and Markdown are delegated to the existing
canonical report renderer, so the structured report remains the source of
truth and infeasible constructions cannot be presented as valid allocations.
