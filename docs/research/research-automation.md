# E3 — Research Automation Architecture

Status: synchronous/local V1 implemented and validated; daemon/queue operation deferred.

This proposal follows `ROADMAP.md` section 19. The target flow is:

```text
new filing / explicit run request
        ↓
automation trigger
        ↓
existing deterministic research pipeline
        ↓
ResearchRun → thesis → changes → watchlist evaluation → report
```

Automation is an execution boundary around the validated research engine. It is
not a new source of metrics, a new strategy runner, or a provider-specific
workflow.

## Current architecture facts

The repository already provides the primitives that automation should compose:

- `ScreeningEngine.run(...)` accepts a frozen `UniverseSnapshot`, supplied
  candidates, strategy identity, parameters, and an optional persistence
  backend. It does not acquire data itself.
- `ResearchRun` and `ResearchResult` are the durable decision records. Strategy
  and universe versions are part of the persisted identity.
- `StructuredThesisEngine`, history comparison, and watchlist evaluation are
  provider-independent consumers of persisted research artifacts.
- `SQLiteStorage` is the current durable store and already persists research,
  thesis, change, watchlist, monitoring, outcome, backtest, and filing records.
- The CLI reads historical artifacts from SQLite; it is not an appropriate
  scheduler or a second research engine.

Consequently, E3 should orchestrate these components through explicit
dependencies and should never hide provider calls inside a scheduled job.

## Event sources

V1 should support a small, explicit set of event sources:

1. **Manual request** — a user supplies an as-of date, universe, strategy, and
   data snapshot. This is the primary deterministic development and recovery
   path.
2. **New filing notification** — a persisted filing document whose public
   availability is after the last completed run and no later than the requested
   run boundary. The event identifies the filing, ticker, form, accession/hash,
   and availability timestamp. It is a trigger, not an input shortcut.
3. **Research schedule** — a calendar decision such as quarterly or daily
   research eligibility. The scheduler emits a run request; it does not select
   securities or calculate metrics.
4. **Explicit watchlist reevaluation** — a new completed `ResearchRun` causes
   existing `WatchlistEntry` conditions to be evaluated. This is driven by
   persisted runs, never by polling prices or providers directly.

Provider callbacks, webhooks, daemons, broker events, and intraday ticks are
outside V1. They can later be translated into the same canonical trigger
record, but must not create a parallel execution path.

## Orchestration versus scheduling

These are separate responsibilities:

### Scheduler

The scheduler answers only: “should a run request be emitted now?” It owns a
clock, schedule definition, timezone, and the last evaluated schedule point.
It produces an immutable request containing:

- trigger type and source identity;
- requested `as_of` and availability boundary;
- universe name/version or an explicit request to resolve a dated snapshot;
- strategy name/version;
- parameters and data snapshot;
- idempotency key.

The scheduler must be deterministic for a supplied clock. V1 should expose a
manual `due_requests(now)` operation and a CLI entry point; an OS scheduler
(cron/launchd/GitHub Actions) may invoke it later.

### Orchestrator

The orchestrator executes one request through the existing pipeline:

1. validate the request and resolve the exact point-in-time universe/data view;
2. acquire and normalize observations through the configured providers/cache;
3. invoke the existing screening/research pipeline;
4. persist the immutable `ResearchRun` and results;
5. generate and persist the thesis snapshot;
6. compare with the prior persisted run when available and persist changes;
7. evaluate watchlist entries against the new run;
8. build/persist or emit the requested report;
9. persist a structured execution result and failure status.

The orchestrator may coordinate these services, but it must not calculate a
ratio, implement a strategy, or silently rerun a historical decision.

## Pipeline reuse and the no-hidden-engine rule

There must be exactly one research path. Automation calls the same explicit
services used by manual research and tests:

```text
Data providers/cache → PIT normalized observations → ScreeningEngine
→ ResearchRun/ResearchResult persistence → ThesisEngine
→ ChangeDetector → WatchlistService → ResearchReportBuilder
```

The automation layer may provide dependency injection, transaction boundaries,
logging, and failure handling. It must not have fallback logic such as “latest
fundamentals”, current-universe substitution, ticker-specific calculations, or
an alternate scoring implementation. A scheduled run is just a run with a
trigger and execution metadata.

## Idempotency and duplicate suppression

Every request needs a stable idempotency key derived from the complete research
identity, not merely ticker and date. V1 key material should include:

```text
as_of + universe name/version + strategy name/version
+ canonical parameters + data snapshot/version + pipeline version
```

For filing-triggered requests, include filing accession/content hash and
availability boundary. Canonical serialization must sort mapping keys and use
normalized dates/enums.

The store should record request state (`accepted`, `running`, `completed`,
`failed`) and the resulting `ResearchRun` ID. A completed key returns the
existing result without executing providers or mutating historical artifacts.
A running key is leased/claimed once; another worker reports `already_running`.
Conflicting requests with the same key must fail rather than overwrite.

Idempotency applies separately to side effects: thesis, change, and monitoring
records use their existing immutable identities/uniqueness rules. Retrying a
successful research run must not create duplicate monitoring events.

## Retries and failure semantics

Retries are safe only for transient acquisition failures and must be bounded.
The policy should classify errors as:

- **Transient**: timeout, connection reset, provider rate limit, or temporary
  5xx. Retry with capped exponential backoff and jitter; record attempts.
- **Permanent input/configuration**: invalid ticker/universe, missing strategy
  version, malformed response, unsupported adjustment policy. Do not retry.
- **Historical integrity failure**: unavailable PIT data, ambiguous filing
  availability, missing required universe snapshot, or provenance mismatch. Do
  not substitute current data; mark the run `blocked`/`insufficient_data` with
  the exact reason.
- **Persistence failure**: roll back the current transaction where possible and
  leave no completed run marker. A later retry must be safe by idempotency key.
- **Downstream reporting/watchlist failure**: preserve the completed research
  decision and record the failed stage separately; do not rerun acquisition
  merely to regenerate a report.

Partial success must be visible. No broad exception swallowing, silent zero
values, or “best effort” historical substitution is acceptable.

## Recommended V1 scope

Implement only the following first slice:

- typed `AutomationRequest`, `AutomationExecution`, trigger, stage status, and
  error records;
- deterministic manual execution of one research request;
- filing-triggered request creation from persisted SEC filing metadata;
- bounded retry policy around provider acquisition, outside domain calculations;
- idempotency claim/complete/fail state in SQLite with additive migration;
- orchestration of the existing research → thesis → changes → watchlist →
  report sequence;
- structured execution logs and CLI `automation run`/`automation status`;
- offline fixture tests, PIT tests, duplicate-trigger tests, retry tests,
  provider-kill-switch tests, close/reopen tests, and crash/retry tests.

Scheduling should initially be a deterministic “due request” library and a
single-run CLI command. An external cron/launchd invocation is sufficient for
real scheduling until operational requirements justify a service.

## Explicit non-goals

E3 V1 must not include:

- a background daemon, distributed queue, or worker cluster;
- live polling, websocket prices, broker integration, or automatic execution;
- a second screening/scoring/strategy implementation;
- current-data fallback for historical runs;
- automatic strategy or threshold optimization;
- LLM, news sentiment, filing NLP, or qualitative claim invention;
- portfolio rebalancing or construction changes;
- dashboard, notifications, email, or push delivery;
- unbounded provider retries or hidden telemetry;
- destructive updates to `ResearchRun`, thesis, outcome, or watchlist history.

## Recommended implementation boundary

When implementation begins, keep the automation package and tests isolated,
for example `src/stocks_investment/automation/` and
`tests/automation/`. It may depend on domain contracts, provider interfaces,
`SQLiteStorage`, screening, thesis, history, watchlist, and reporting. It must
not modify those feature implementations to add automation-specific behavior.
Any new persistence should be additive and limited to automation request and
execution state; derived research products remain in their existing tables.

The first integration test should create a filing-triggered request, execute it
with deterministic fixtures, close/reopen SQLite, submit the same request
again, and prove that the original `ResearchRun`, thesis, changes, watchlist
events, and report are reused without provider calls or duplicate side effects.

## Required report

WORKSTREAM: E3-RESEARCH
STATUS: Architecture research complete; implementation not started.
Scope completed: Event sources; scheduler/orchestrator boundary; pipeline reuse; idempotency; retry and failure semantics; V1 scope; non-goals.
Files created: `docs/research/research-automation.md`
Files modified: None
Tests added: None; this workstream is documentation-only.
Tests executed: Read-only repository inspection; no mutating formatting tools.
Results: Recommended a single deterministic orchestration path around existing validated research services, with manual/filing/schedule/watchlist triggers and SQLite-backed idempotency.
Assumptions: Existing `ResearchRun`, PIT data, storage uniqueness, thesis/history/watchlist/report services remain the source of truth; external scheduling may invoke a deterministic due-request operation.
Known limitations: No implementation, migration, operational scheduler, distributed locking, or live provider behavior was changed or validated.
Dependencies on other workstreams: E3 implementation depends on the existing E0–E2 contracts and providers; it must coordinate with storage and CLI owners through approved shared-contract changes.
Recommended next action: Freeze E3 automation contracts and an additive persistence plan, then implement the offline single-request/idempotency slice behind a strict directory fence.
