# Wave E5 persistence plan

E5 adds no durable domain entity and no SQLite migration. Interactive sessions,
navigation history and rendered views are transient derived products.

The interface opens an existing migrated database in explicit read-only mode.
It must not create a missing path, create parent directories, run migrations,
write caches, persist a session, update a watchlist or refresh provider data.

Close/reopen tests use a writer to prepare fixtures, close it, then open the E5
reader. Mutation attempts through that reader must fail and historical views
must remain deterministic.
