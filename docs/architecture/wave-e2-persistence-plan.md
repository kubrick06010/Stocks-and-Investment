# Wave E2 persistence plan

SQLite schema v8 will add tables for filing documents, normalized sections,
qualitative claims, section changes and evidence snapshots. Raw bytes remain in
the content-addressed `raw_payloads` cache; document rows retain the hash and
stable SEC identity. Evidence references are normalized JSON containing only
stable IDs, offsets and hashes.

The migration is additive and idempotent. A v7 database must retain all Waves
B–E1 artifacts. Every E2 entity must survive close/reopen without provider
access. Immutable IDs are insert-once: conflicting content under an existing
filing/section/claim ID is an error rather than `INSERT OR REPLACE` history
mutation.
