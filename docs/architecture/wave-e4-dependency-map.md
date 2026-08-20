# Wave E4 dependency and ownership map

```text
domain/portfolio_construction + interfaces/portfolio_construction (frozen)
        |
        +-- E4A weighting engine
        +-- E4B constraints and feasibility
        +-- E4C turnover/cost/trade plan
        +-- E4D SQLite v10 persistence
        +-- E4E backtest/report integration
        +-- E4F adversarial economic reconciliation
```

Feature agents own disjoint files under `portfolio_construction/`. They may
consume persisted research and validated backtest/portfolio helpers but cannot
modify scoring, screening, ledger, analytics or shared contracts.
