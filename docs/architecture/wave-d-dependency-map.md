# Wave D dependency map and ownership

| Workstream | Owns | Depends on | Must not modify |
|---|---|---|---|
| D1 Thesis | `src/stocks_investment/thesis/`, `tests/thesis/`, thesis methodology | ResearchRun/Result, FactorScore, CriterionResult | history, comparison, research, watchlist, reporting |
| D2 History | `src/stocks_investment/history/`, `tests/history/` | D1 contracts, persisted runs | thesis domain contracts, storage implementation |
| D3 Comparison | `src/stocks_investment/comparison/`, `tests/comparison/` | persisted runs/backtests | thesis, efficacy, watchlist |
| D4 Efficacy | `src/stocks_investment/research/`, `tests/research/` | FactorScores + Outcomes + CohortIdentity | backtesting, strategy implementations |
| D5 Watchlist | `src/stocks_investment/watchlist/`, `tests/watchlist/` | new ResearchRuns, D1/D2 contracts | providers, polling, brokers |
| D6 Reporting | `src/stocks_investment/reporting/`, reporting tests, CLI edge only | all read-only services | domain calculations, historical records |

The Program Lead owns shared domain/interfaces and the Integration agent owns
cross-module reconciliation. No implementation workstream may edit another's
directories.
