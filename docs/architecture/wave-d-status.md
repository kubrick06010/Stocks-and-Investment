# Wave D status

| Workstream | Status | Implementation |
|---|---|---|
| D0 contract freeze | VALIDATED | domain/interfaces/docs/tests complete |
| D1 Thesis | VALIDATED | four-run persistence, version isolation, outcome immutability, provider-free inspection |
| D2 History/change detection | VALIDATED | material transitions, ticker identity, reopen, and outcome isolation |
| D3 Strategy comparison | VALIDATED | complete represented fairness matrix, persisted performance, deterministic incompatibility |
| D4 Factor efficacy | VALIDATED | SQLite v6 cohort identity, migration, mixing attacks, persisted CLI/report path |
| D5 Watchlists/monitoring | VALIDATED | multi-run trigger, duplicate suppression, outcome isolation, reopen |
| D6 Reporting/CLI | VALIDATED | seven-command matrix, text/JSON/Markdown, lineage, research/outcome barrier |
| Wave D.6 integration | VALIDATED | shared fixture, provider kill switch, future/version/order attacks, deterministic reopen |

Wave D closure used Luna Medium agents behind disjoint directory fences for D3,
D6, and adversarial E2E work. Shared domain/storage changes were performed only
by the lead integrator. All Wave D historical inspection succeeds after SQLite
reopen with provider and HTTP kill switches active.
