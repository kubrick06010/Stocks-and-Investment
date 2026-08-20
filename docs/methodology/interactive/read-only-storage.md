# Read-only SQLite storage

`ReadOnlySQLiteStorage` is the persistence boundary for interactive research
inspection. It reuses the validated `SQLiteStorage` read methods, but creates
its own SQLite connection and never invokes the write-capable constructor or
migration routine.

The adapter accepts only an explicit existing regular filesystem path. The
path is resolved strictly, control characters and URI schemes are rejected,
and the file must have a SQLite database header. It does not create missing
files or parent directories.

The connection uses SQLite `mode=ro` and enables `PRAGMA query_only`. Therefore
inherited save methods fail with SQLite's write-protection error and direct
migration attempts are rejected by the adapter. The database schema and data
remain unchanged. `path` exposes the resolved path, and normal `close()` and
context-manager lifecycle methods are supported.

This is intentionally a local, provider-free read path. It does not refresh
prices, fundamentals, universes, or any other current data while rendering
historical research artifacts.
