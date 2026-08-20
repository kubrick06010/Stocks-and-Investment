# Wave E3 persistence plan

Use additive SQLite v9 tables for automation definitions, triggers and runs.
Step results are a bounded structured collection within the immutable run
record. Existing B–E2 tables remain unchanged. Stable references point to
existing filings, ResearchRuns, ThesisSnapshots, change events, monitoring
events and reports where durable.

Definitions and triggers are immutable. A run may advance only through valid
status transitions; terminal economic/history content is immutable. Step
results retain attempts, typed failures and input/output references. A unique
idempotency key prevents duplicate execution for the same definition version
and trigger.

Migration tests must prove v8-to-v9 preservation, repeatability, close/reopen
and conflict rejection. No execution queue or scheduler state is required for
V1.
