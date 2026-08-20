# Wave D persistence plan

The Wave D entities are:

- `thesis_snapshots` and structured drivers/assumptions/invalidators;
- `research_change_events` with old/new values and source references;
- `watchlist_entries` and `monitoring_events`;
- durable `factor_outcome_observations` with complete cohort identity;
- efficacy/comparison summaries remain deterministic derived products.

The existing SQLite storage facade should be extended through small capability
methods or repositories after an implementation contract review. Do not create
one protocol per table and do not create a universal God interface. Every
table must retain methodology versions and historical source IDs. Migrations
must be additive, repeatable from an empty database, and tested on reopen.

User-authored watchlist notes are persisted as data, not transmitted anywhere;
there is no telemetry or hidden external service.

SQLite schema v6 adds `factor_outcome_observations` additively over v5. Existing
research, backtest, thesis, change, and watchlist records remain readable.
