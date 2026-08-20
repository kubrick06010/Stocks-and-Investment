# Wave D historical fixture

The authoritative Wave D integration story is implemented in
`tests/e2e/test_wave_d_historical_intelligence.py`. It uses one synthetic
universe, five securities and four persisted research dates:

| Date | Run |
| --- | --- |
| 2024-03-31 | `run-0` |
| 2024-06-30 | `run-1` |
| 2024-09-30 | `run-2` |
| 2024-12-31 | `run-3` |

The companies are `AAA`, `BBB`, `CCC`, `DDD` and `EEE`. The fixture persists
research runs/results, factor scores, criterion results, outcomes, thesis
snapshots, change events, watchlist events and C6 backtests in the same SQLite
database. It is intentionally synthetic: it validates identity, persistence,
versioning and information barriers, not investment performance.

## Adversarial guarantees

The E2E tests cover:

- provider and HTTP kill switches after database close/reopen;
- a future `+500%` outcome that cannot mutate the T0 thesis, changes,
  monitoring events or backtest;
- additive thesis and strategy versions, with v1 artifacts retained;
- order shuffling of research results, checked by ticker identity rather than
  positional alignment;
- deterministic report structure and deterministic reopened artifacts;
- explicit `research` versus `outcome` report sections in JSON and Markdown;
- persisted strategy comparison, factor efficacy and watchlist inputs.

The CLI is exercised only as a reader of persisted SQLite state. If a provider,
HTTP transport, current-price lookup or current-fundamental lookup is touched,
the test fails immediately through the kill switch.

## Closure contract

`FactorOutcomeObservation` now persists factor version, universe, benchmark,
horizon, base currency, and rebalance cadence. D4 rejects a population when any
observation differs from the requested cohort. SQLite schema v6 adds these
records without rewriting historical Wave B/C/D tables.

The CLI imports the single public `build_historical_stock_report` builder and
its command matrix reads the reopened SQLite database only. Provider and HTTP
kill switches protect the historical inspection path.
