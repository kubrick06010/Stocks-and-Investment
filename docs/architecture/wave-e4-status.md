# Wave E4 status

| Workstream | Status | Evidence |
|---|---|---|
| E4.0 contracts | VALIDATED | 7 contract tests; frozen domain/service seam |
| E4A weighting | VALIDATED | equal and score-proportional persisted-result weighting; identity/order attacks pass |
| E4B constraints | VALIDATED | long-only, position/sector/cash/turnover evaluation; infeasibility remains explicit |
| E4C turnover/costs | VALIDATED | ticker-keyed union; zero/partial turnover and funded-cost reconciliation pass |
| E4D persistence | VALIDATED | additive SQLite v10 migration; immutable policy/request/result close-reopen |
| E4E integration/reporting | VALIDATED | persisted ResearchRun to target/trades/report E2E; deterministic replay |
| E4F adversarial review | VALIDATED | 9 independent attacks; no release-blocking defect demonstrated |
| E4 integration | VALIDATED | 416 passed, 1 intentional live-provider skip; ruff/mypy/compileall/diff green |

V1 deliberately rejects transaction costs that cannot be funded by explicit
target cash. Sector caps also fail rather than using undated/current sector
classifications because the frozen request does not yet carry a point-in-time
sector snapshot.
