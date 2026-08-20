# V2 program status

| Workstream | Agent | Branch | Status | Blocked by | Tests | Ready to merge |
|---|---|---|---|---|---|---|
| Legacy forensics | 1 | unavailable (`.git` is read-only) | VALIDATED | none | compile audit | yes |
| Formula audit | 2 | unavailable | VALIDATED | none | source review | yes |
| Runtime/dependencies | 3 | unavailable | VALIDATED | none | compile/import probes | yes |
| Data-provider research | Luna Medium fenced research | unavailable | VALIDATED | none | official-source review 2026-08-19 | yes |
| Backtest research | Luna Medium fenced research | unavailable | VALIDATED | none | official-source review 2026-08-19 | yes |
| Competitive landscape | Luna Medium fenced research | unavailable | VALIDATED | none | official-source review 2026-08-19 | yes |
| Architecture | 4 | unavailable | VALIDATED | none for baseline contracts | 5 unit tests | yes |
| Data core | 6 | unavailable | VALIDATED | foundation provider contract | 5 unit tests | yes |
| Provenance/storage | 7 | unavailable | VALIDATED | none for foundation slice | 4 unit tests | yes |
| Foundation CLI | 19 + D6 integration | unavailable | VALIDATED | none | CLI + provider-kill-switch E2E | yes |
| Foundation vertical slice | Lead | unavailable | VALIDATED | none | 13 tests | yes |

| Wave B1 fundamentals | B1 | unavailable | VALIDATED | none for B1.5 gate | 13 tests + provenance integration | yes |
| Wave B2 technical | B2 | unavailable | VALIDATED | protocol decision optional | 7 tests | yes |
| Wave B3 portfolio | B3 | unavailable | VALIDATED | valuation/FX integration deferred | 4 tests | yes |
| Wave B4 providers | B4 | unavailable | VALIDATED | live credentials/network intentionally deferred | 6 tests + integration | yes |
| Wave B5 golden validation | B5 | unavailable | VALIDATED | none for independent fixture gate | 6 golden tests | yes |
| Wave B integration | Lead | unavailable | VALIDATED | none for Wave B.5 | 46 tests, 1 live skipped | yes |

| Wave C.0 contract freeze | Lead/Architect | unavailable | VALIDATED | none | 8 contract tests; 54 total | yes |
| C1 Graham strategies | agent/local ownership | unavailable | VALIDATED | criteria and versions survive screening persistence | 20 focused + historical E2E | yes |
| C2 Quality/forensics | agent/local ownership | unavailable | VALIDATED | none for isolated factor models | quality factor tests; full suite green | yes |
| C3 Scoring | agent/local ownership | unavailable | VALIDATED | C0 contracts | 14 agent tests + 3 focused tests | yes |
| C4 Screening | agent/local ownership | unavailable | VALIDATED | exact universe and components persist/reopen | 4 focused + persistence/E2E | yes |
| C5 Portfolio analytics | lead/local ownership | unavailable | VALIDATED | date-aligned benchmark analytics implemented | analytics + alignment tests | yes |
| C6 Backtesting | lead/local ownership | unavailable | VALIDATED | V1 scope: equal-weight persisted-run simulation; action execution remains explicit/raw-only | 15 focused + full suite | yes |

| Wave C.5 integration | Program Lead | unavailable | VALIDATED | all Wave C closure gates pass; V1 limitations documented | 99 passed, 1 skipped | yes |

| Wave C.6 final closure | Program Lead | unavailable | VALIDATED | none within V1 closure scope | 99 passed, 1 skipped | yes |

| Wave D.0 architecture freeze | Program Lead/Architect | unavailable | VALIDATED | none; implementation intentionally blocked | 6 contract tests | yes |
| D0.5 Storage extension | Program Lead | unavailable | VALIDATED | additive SQLite v5 migration | storage round-trip tests | yes |
| D1 Thesis | local ownership | unavailable | VALIDATED | none | thesis + version/outcome E2E | yes |
| D2 History/change detection | local ownership | unavailable | VALIDATED | none | history + identity/outcome E2E | yes |
| D3 Strategy comparison | Luna Medium / lead integration | unavailable | VALIDATED | none | 17 focused + shared E2E | yes |
| D4 Factor efficacy | lead integration | unavailable | VALIDATED | none | 11 cohort/storage/migration tests + E2E | yes |
| D5 Watchlists | local ownership | unavailable | VALIDATED | none | watchlist + provider-kill-switch E2E | yes |
| D6 Reporting/CLI | Luna Medium / lead integration | unavailable | VALIDATED | none | 29 focused + provider-free E2E | yes |

| Wave D implementation coordination | Program Lead + fenced Luna Medium agents | unavailable | VALIDATED | none | 166 passed, 1 skipped | yes |

| Wave D.6 final closure | Program Lead | unavailable | VALIDATED | all roadmap P0/P1 release blockers closed | 166 passed, 1 skipped | yes |

| Wave E.0 statistical contracts | Program Lead/Architect | unavailable | VALIDATED | none | 7 contract tests; 173 total, 1 skipped | yes |
| Wave E.1 statistical implementation | fenced Luna Medium workstreams + Program Lead | unavailable | VALIDATED | none | 245 passed, 1 skipped; adversarial review | yes |
| Wave E.2 qualitative filings contracts | Program Lead/Architect | unavailable | VALIDATED | none | 6 contracts; 251 total, 1 skipped | yes |
| Wave E.2 qualitative filings implementation | fenced Luna Medium workstreams + Program Lead | unavailable | VALIDATED | none within V1 scope | 304 passed, 1 skipped; adversarial review | yes |
| Wave E.3 research automation contracts | Program Lead/Architect | unavailable | VALIDATED | none | 7 contracts; 311 total, 1 skipped | yes |
| Wave E.3 research automation implementation | fenced Luna Medium workstreams + Program Lead | unavailable | VALIDATED | none within synchronous V1 scope | 366 passed, 1 skipped; 11 adversarial attacks | yes |
| Wave E.4 portfolio construction contracts | Program Lead/Architect | unavailable | VALIDATED | none | 7 contracts; 373 total, 1 skipped | yes |
| Wave E.4 portfolio construction implementation | fenced Luna Medium workstreams + Program Lead | unavailable | VALIDATED | none within deterministic long-only V1 scope | 416 passed, 1 skipped; 9 adversarial attacks | yes |
| Wave E.5 interactive research contracts | Program Lead/Architect + fenced Luna Medium review | unavailable | VALIDATED | none | 6 contract tests; 422 total, 1 skipped | yes |
| Wave E.5 interactive research implementation | Program Lead + fenced Luna Medium workstreams | unavailable | VALIDATED | none within local read-only V1 scope | 461 passed, 1 skipped; adversarial/interface E2E | yes |
| Wave E.6 narrative contracts | Program Lead/Architect | unavailable | VALIDATED | none | typed evidence-bound narrative contracts | yes |
| Wave E.6 narrative implementation | Program Lead | unavailable | VALIDATED | no external LLM/provider in V1 | 470 passed, 1 skipped; renderer/CLI/barrier tests | yes |
| Wave E integration | Program Lead | unavailable | VALIDATED | local offline V1 scope | 481 passed, 1 skipped; full quality gates | yes |
| E1 real-data PIT pilot | Program Lead + fenced Luna Medium reviewer | unavailable | VALIDATED AS INTEGRATION PILOT | full-panel delivery pending; economic conclusions remain NO-GO | 11 artifact/pilot tests; 638 real factor-outcome rows; deterministic SQLite rerun | yes, with no economic claim |
| E1 full economic dataset | external acquisition | unavailable | BLOCKED | publisher response or user-approved commercial license | public access request + acceptance checklist | no |

Scientific evidence boundary: E1 machinery is validated against deterministic
fixtures and one bounded real CC BY sample. The sample validates acquisition,
normalization, PIT filtering and persistence, not profitability. A large
licensed panel with historical membership and economically defined delistings
is still required before any factor or strategy claim is treated as economic
evidence. See `docs/architecture/roadmap-completion-audit.md`.

The external-artifact boundary is implemented and tested with archive/member
hashes, license/source identity, schema, duplicate-identity and missing-value
guards. Raw data remains ignored; only its manifest and bounded-pilot evidence
are tracked. The source is not represented as authoritative for economic use.

## Wave C execution control

- The environment rejected both new and resumed subagent work with `agent thread limit reached`; no fake parallelism was used. Work continued in disjoint logical ownership directories in the writable tree.
- C3 and C4 delivered implementation work without modifying frozen shared contracts. C1, C5 and C6 were integrated in the writable tree with directory ownership preserved; C2 quality code received only local type/test hardening.
- C4's requested `universe_version` and persisted factor/criterion detail are now implemented through the minimal ResearchRun/ResearchResult and SQLite schema changes.

## Wave B controls

- Git branch/worktree isolation remains unavailable because the sandbox prevents `.git` ref writes. Fallback remains directory ownership plus isolated logical workstreams.
- Shared domain/interface contracts are frozen for this wave. Agents must submit change requests rather than edit them independently.
- Storage protocol watch item: `StorageBackend` and `ResearchStorageBackend` are currently sufficient. Additional capability protocols require a lead review to avoid a fragmented or God-interface persistence design.

Git branch/worktree isolation is unavailable because the sandbox prevents `.git` ref writes. Fallback: directory ownership and isolated logical workstreams. The working branch remains `master`; no further branch/worktree attempts should be made unless the environment changes.
