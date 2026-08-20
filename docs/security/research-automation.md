# Security and reliability review: E3 research automation

Status: synchronous/local V1 validated. Concurrent/background execution remains
design-only and must not be enabled without the additional controls below.

Scope: the roadmap flow

```text
new filing -> new observations -> ResearchRun -> thesis -> changes
           -> watchlist evaluation -> report
```

The automation layer must orchestrate the existing deterministic pipeline. It
must not become a second research engine, bypass point-in-time access, rerun a
historical decision with current data, or turn a schedule into permission to
execute arbitrary code.

The current repository provides useful security boundaries: named
provider adapters, bounded HTTP retries/timeouts, SQLite persistence, versioned
ResearchRuns, PIT availability fields, immutable Wave D artifacts, and a
read-only historical CLI. E3 currently has no scheduler, daemon, queue,
webhook endpoint, or automation-specific persistence. The controls below are
The implemented V1 adds typed triggers, bounded retry decisions, secret-bearing
parameter rejection, redacted errors, full-identity idempotency, SQLite v9
round-trips, PIT filing triggers, outcome-reference rejection and a provider-
free reopen test. Multiworker leasing, crash resume, quotas and a runtime kill
switch remain requirements for any future daemon/queue deployment.

## Security objectives and trust boundaries

The automation trust boundary should be explicit:

```text
operator/config -> validated job definition -> scheduler/runner
provider/network -> bounded acquisition -> normalized/PIT data
                                      -> deterministic research pipeline
                                      -> immutable ResearchRun/artifacts
                                      -> report/watchlist outputs
```

Schedules, event payloads, provider responses, paths, symbols, and filing
content are data, not instructions. Only a registered job type and a validated
configuration may select work. No job may supply a Python import path, shell
command, SQL fragment, URL, template, or arbitrary callable.

The runner should operate with a separate local identity and least-privilege
filesystem access. Historical inspection after persistence must remain
provider-free. Network acquisition belongs only to the explicitly enabled
ingestion step; thesis, change, watchlist, factor, and report steps consume
persisted artifacts.

## Threat register and required controls

| Threat | Impact | Required E3 control | Evidence/test required |
|---|---|---|---|
| Secret in environment, config, command line, job payload, URL, or logs | API-key disclosure, provider impersonation, privacy breach | Read secrets only from an approved environment/OS-secret boundary. Never persist them in job definitions, ResearchRuns, SQLite parameters, reports, exception text, metrics, or URLs. Redact authorization headers, cookies, query strings, and filesystem credentials before logging. | Secret-canary integration test through every failure and retry path; inspect persisted JSON, logs, CLI output, and exception strings. |
| Untrusted schedule fields or event payloads | Code execution, arbitrary provider access, resource abuse | Parse into a typed allowlisted job definition. Reject unknown fields, shell fragments, import paths, arbitrary URLs, unsafe time zones, excessive intervals, and unbounded symbols/date ranges. Use a fixed registry of job kinds. | Fuzz malformed JSON/config/events; assert rejection before execution and no network/file/process side effect. |
| Path/config injection | Read/write outside the configured database/cache, secret-file disclosure | Expand only an explicitly configured storage path; reject NUL, traversal, unexpected schemes, and path-like provider identifiers. Resolve and verify containment for cache/output paths. Do not use user input as a shell command or SQL identifier. | Absolute, relative, `..`, symlink, NUL, URI, and shell-metacharacter fixtures; assert no outside access. |
| Duplicate scheduler delivery or retry | Duplicate ResearchRuns, duplicate watch events, inflated outcomes, repeated provider cost | Derive an idempotency key from job kind, ticker/universe, as-of, strategy/version, data snapshot, and methodology version. Enforce it transactionally in SQLite. A completed key is a no-op; an identical in-flight key is coalesced/rejected; a conflicting payload is a hard error. | Execute the same job concurrently and after simulated retry/restart; assert one ResearchRun and one downstream immutable artifact set. |
| Replay of an old event | Reprocessing stale data or silently changing historical state | Persist event ID, received time, source, payload hash, schema version, and processed status. Require replay policy to be explicit. Replaying an already completed event must not overwrite artifacts; a new methodology/version must create a new run, never mutate the old one. | Replay identical and old events in different orders; compare artifact hashes, lineage, and counts. |
| Race between overlapping runs | Two runs observe different inputs or both publish inconsistent watchlist state | Use a durable run state machine (`RECEIVED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`) with compare-and-set transitions and a single authoritative commit boundary. Serialize per research identity/ticker where writes conflict; allow parallel work only for disjoint identities. | Barrier-controlled two-worker test; assert no duplicate IDs, partial “success”, or lost monitoring transition. |
| Crash after an intermediate step | Orphaned raw data, half-persisted ResearchRun, thesis without evidence, misleading report | Treat acquisition/normalization and final research publication as explicit transactions or resumable stages. Publish the ResearchRun only after all required inputs and lineage are committed. Mark failed attempts; do not convert partial state to success. | Inject failure after each stage and restart; assert recoverable status, no trusted incomplete result, and deterministic resume/no-op behavior. |
| Provider rate limits or retry storms | Quota exhaustion, denial of service, provider ban, correlated duplicate data | Reuse bounded provider retry/error taxonomy. Apply per-provider and global rate limits, finite exponential backoff with jitter only if methodology permits, `Retry-After` handling, circuit breaking, cancellation, and a concurrency cap. Never retry parsing, schema, auth, or PIT validation failures. | Fake 429/5xx/timeout provider; assert bounded attempts, no concurrent storm, clear status, and no silent missing-as-zero observation. |
| Provider response changes between retries | Non-reproducible inputs or mixed vintages in one run | Pin retrieval time and response/content hash per observation. A retry may complete the same acquisition, but the run must record the actual snapshot used. Never silently merge payloads from different retrievals. | Return different bodies on retry; assert raw hashes and data snapshot distinguish the result or the run fails explicitly. |
| Future filing/price becomes physically available before an old job runs | Look-ahead bias in a supposedly historical run | Every job carries an immutable `as_of`. Use the existing PIT access semantics (`available_at`/effective availability, not period end or retrieval time). A delayed job for T0 must execute against T0’s information set or be rejected as stale; it must never query “latest”. | Store future filing, price, universe member, and outcome before executing T0; assert none can reach strategy inputs. |
| Clock manipulation or ambiguous timezone | Runs attributed to the wrong availability date or duplicate cadence window | Use UTC internally, persist received/started/finished timestamps, and inject a trusted clock in tests. Schedule evaluation must use an explicit timezone and ISO-8601 policy; DST ambiguity is rejected or resolved deterministically. The clock must not replace provider-public availability timestamps. | DST boundary, leap day, clock rollback, and future local-time fixtures; assert stable run identity and PIT decisions. |
| Unbounded schedule frequency, universe, or date range | CPU, memory, disk, provider quota, or SQLite exhaustion | Enforce quotas: maximum tickers, date window, filings, retries, output bytes, wall-clock/runtime, and concurrent jobs. Require explicit operator approval for a larger batch. Cancellation must leave a truthful failed/cancelled status. | Oversized job fixture; assert preflight rejection and bounded resource use. |
| Queue starvation or denial through many low-priority jobs | Critical research/watchlist work never executes | Use bounded queues, per-source fairness, priority limits, and admission control. Do not allow an event source to enqueue unbounded work. Expose queue depth and rejected/coalesced counts without leaking payloads. | Flood test with one source and a critical job; assert bounded queue and fair admission. |
| Watchlist transition race | Duplicate or contradictory MonitoringEvents; wrong previous state | Evaluate a watch condition against a specific persisted ResearchRun and previous persisted state. Persist transition with a uniqueness constraint on entry/run/condition. Do not evaluate from mutable current provider data. | Two workers process the same ResearchRun; assert one deterministic transition and no duplicate trigger. |
| ResearchRun publication without complete lineage | A report or thesis cannot be audited; unverifiable automated decision | Require references to data snapshot, strategy/version, universe snapshot/version, input observations, provenance, git/calculation versions, and automation event/job identity before success. Missing required lineage is `FAILED`/`INSUFFICIENT_DATA`, never a warning-only success. | Attempt to publish with one missing reference; assert rejection and no successful run. |
| Mutable retry/configuration changes historical interpretation | Past thesis or outcome silently changes after deployment | Store full normalized parameters, methodology versions, provider/data snapshot IDs, and automation config hash. Immutable Wave D/E artifacts remain insert-once. A config change creates a new run identity. | Run same as-of with changed threshold/version; assert separate IDs and unchanged old artifacts. |
| Provider/network access from post-persistence steps | Reopened historical report depends on current internet or leaks data | Separate acquisition from analysis services. Add a provider kill switch to automation tests and run thesis/change/watchlist/report after close/reopen. A provider invocation in these steps is a release failure. | Guard every provider entry point to raise after persistence; historical workflow must still pass. |
| Malicious filing/event text used as instructions | Prompt injection, shell/template/Markdown injection, false rationale | Treat external text as untrusted evidence. Escape terminal/JSON/Markdown output, do not evaluate templates or execute embedded links/scripts, and keep a future LLM out of the automation core. Claims require evidence references and must not create jobs. | Event/filing containing shell commands, ANSI, HTML, fake system instructions; assert inert storage and escaped reports. |
| Unsafe deserialization of persisted job state | Code execution or arbitrary object creation | Persist JSON primitives under a schema version; validate against typed models. Never use pickle, `eval`, arbitrary YAML constructors, or importable class names. Unknown schema versions fail closed. | Malformed and gadget-shaped payload fixtures; assert safe parse failure and no side effects. |
| Unbounded raw payload/cache growth | Disk exhaustion and loss of availability | Enforce provider response, cache, raw payload, and report quotas; deduplicate by content hash; use atomic writes and transactional SQLite inserts. Define retention separately from immutable research lineage. | Repeated identical and oversized payloads; assert bounded growth and no corrupt migration. |
| Audit log tampering or insufficient audit trail | Cannot prove who/what/when produced a decision | Persist append-only automation run/event records with actor, job definition hash, input snapshot IDs, output IDs, state transitions, timestamps, error class, and code/methodology versions. Never log secrets or full sensitive payloads. Hash-chain or external append-only storage may be a later hardening option. | Close/reopen audit round-trip; compare event/output lineage; attempt duplicate/conflicting event insertion and assert detection. |
| Excessive telemetry or user-data leakage | Watchlist notes, symbols, filings, or strategy choices sent to third parties | Default to local structured logs only. No hidden telemetry. Redact user notes and raw filings; document opt-in export, retention, and destination. Aggregate operational counters where possible. | Search logs/reports for secret, note, raw filing, and authorization canaries; assert absence or explicit opt-in boundary. |
| Over-privileged runner | Compromise can modify source, credentials, or unrelated user data | Run with least-privilege OS account, database/cache-only write permissions, no shell, no arbitrary subprocess, no network except named provider hosts, and read-only access to code/config. Separate provider credentials by capability. | Permission-boundary test or documented deployment checklist; attempt write/network/process operations outside allowlist. |
| Kill switch unavailable or too coarse | Operator cannot stop a runaway or unsafe automation job | Provide a local, authenticated/operator-controlled kill switch that stops admission and cancels queued/running work at safe checkpoints. It must not delete history or roll back published immutable artifacts. Record who/when/reason. | Trigger during acquisition and before publication; assert no new trusted output after stop, truthful cancelled status, and prior history intact. |
| Silent failure or “best effort” completion | Missing securities look successful; incomplete factor efficacy appears credible | Return explicit per-step/per-symbol statuses and aggregate status. Distinguish `FAILED`, `CANCELLED`, `INSUFFICIENT_DATA`, `STALE`, and `SUCCEEDED`. No empty/zero fallback for missing financial data. | Missing filing, provider quota, parse error, and partial universe fixtures; inspect status and reports. |
| Unsafe notification/report destination | Research data or secrets sent to arbitrary recipients | Keep V1 local and synchronous; no email/webhook/push delivery. If later added, use named destinations, allowlists, redaction, size limits, signed requests, and explicit user consent. | Attempt arbitrary URL/recipient in config; assert rejected and no outbound request. |

## Deterministic execution contract

The minimum safe E3 execution record should include:

- automation event ID and source/payload hash;
- job kind and schema version;
- idempotency key and retry/attempt number;
- requested `as_of`, explicit timezone, and injected/current UTC timestamps;
- ticker/universe identity, strategy and strategy version;
- data snapshot/provider response hashes and PIT policy;
- calculation/thesis/factor methodology versions;
- state transitions and per-step statuses;
- ResearchRun, ThesisSnapshot, ChangeEvent, MonitoringEvent, and Report IDs;
- actor/config hash, cancellation reason, and normalized error class.

The same validated job definition and persisted information set must produce
the same economic artifacts. Timestamps, attempt IDs, and operational logs may
differ, but selection, scores, thesis content, changes, watch transitions, and
lineage must not. A replay with a different methodology or data snapshot is a
new run and must be visibly versioned.

## Safe V1 sequencing

1. Start with a manually invoked, offline-capable runner over persisted
   inputs. Do not begin with a daemon, webhook, or background scheduler.
2. Add typed job definitions, preflight quotas, idempotency, durable state, and
   the kill switch before enabling periodic schedules.
3. Run acquisition in a bounded provider boundary. Commit raw/normalized
   observations and provenance before invoking deterministic research.
4. Construct a ResearchRun only after the complete required information set is
   available and PIT-validated. Partial jobs remain explicitly incomplete.
5. Generate thesis, change events, watchlist events, and reports from the new
   persisted run. These steps must have a provider-kill-switch test.
6. Make event replay and crash recovery deterministic before adding concurrent
   workers. Then add bounded per-identity concurrency with transactional
   idempotency.
7. Keep notifications, remote control, arbitrary scheduling expressions, and
   external telemetry out of V1.

## Required adversarial test matrix

- duplicate delivery, concurrent duplicate workers, replay after success, and
  conflicting same-key payload;
- crash/failure after acquisition, normalization, ResearchRun publication,
  thesis generation, and watchlist evaluation;
- T0 execution while T1 filings, prices, universe members, outcomes, and
  strategy versions physically exist in SQLite;
- provider 429, 5xx, timeout, malformed response, changed retry response,
  oversized response, and retry-budget exhaustion;
- malformed schedule/event JSON, unknown fields, unsafe paths, bad timezones,
  oversized universe/date range, and shell/import/URL injection;
- two workers racing the same watch condition and two runs racing a shared
  ticker; assert identity-safe unique results;
- secret canaries through errors, logs, persisted config, reports, and
  provider headers;
- kill switch during each long-running stage and restart after cancellation;
- DB close/reopen followed by provider-killed thesis, changes, watchlist, and
  report inspection;
- deterministic rerun from the same persisted data snapshot and methodology;
- audit trail round-trip, conflicting immutable insert, and corrupted job
  payload/schema version.

## Residual risks and explicit non-goals

- A local SQLite database is not a hostile multi-tenant queue. File-system
  permissions, backups, encryption at rest, and operator access remain host
  responsibilities unless separately designed and tested.
- A scheduler cannot make provider data authoritative. SEC/public availability,
  provider completeness, restatements, delistings, and historical universe
  coverage remain data-quality risks.
- Idempotency prevents duplicate logical publication, but it does not make a
  provider response immutable. Response hashes and data snapshots are required
  for reproducibility.
- A kill switch at safe checkpoints may not interrupt a blocking network call
  immediately; timeouts and cancellation-aware transports are required.
- At-least-once delivery is the safer assumed event model. Exactly-once
  external side effects are not claimed; immutable local commits plus
  idempotency are the boundary.
- No live trading, broker execution, automatic portfolio mutation, arbitrary
  webhooks, email/push notifications, LLM processing, or strategy optimization
  belongs in E3.

## Security acceptance gate

Before enabling concurrent or background E3 execution, all of the following
operational controls require evidence:

- [ ] typed allowlisted jobs and validated schedules/events;
- [ ] no secrets in source, payloads, SQLite, logs, or reports;
- [ ] idempotency and replay protection under concurrent delivery;
- [ ] explicit durable state machine and crash recovery;
- [ ] bounded retries, rate limits, quotas, cancellation, and kill switch;
- [ ] no path/config/shell/import/URL injection;
- [ ] PIT enforcement when future data is physically present;
- [ ] provider-free post-persistence analysis and report inspection;
- [ ] complete immutable lineage from event to ResearchRun and outputs;
- [ ] least-privilege deployment and no hidden telemetry;
- [ ] adversarial tests above pass offline;
- [ ] `ruff`, `mypy`, `pytest`, `compileall`, and `git diff --check` pass.

## Required workstream report

WORKSTREAM: E3-SECURITY
STATUS: REVIEW — threat/reliability design only; no production automation approved
Scope completed: secrets, untrusted schedules/events, duplicate execution, replay, race/concurrency, partial failure, provider rate limits, path/config injection, telemetry/privacy, audit trail, least privilege, kill switch, PIT and information barriers.
Files created: `docs/security/research-automation.md`
Files modified: none
Tests added: none; this workstream is documentation-only
Tests executed: read-only repository inspection; no production test command run
Results: E3 risks, controls, sequencing, residual risks, and an adversarial acceptance matrix documented.
Assumptions: E3 will orchestrate existing deterministic research services and use persisted, versioned artifacts; V1 remains local/offline-first with named providers and no arbitrary callbacks.
Known limitations: no scheduler/orchestrator implementation exists to verify; deployment isolation, secret storage, backup encryption, and provider historical completeness require later operational evidence.
Dependencies on other workstreams: E3 contracts/storage/idempotency must be frozen before implementation; it depends on existing PIT, provenance, ResearchRun, Wave D immutability, provider error, and reporting boundaries.
Recommended next action: architecture-freeze E3 job/event/state/idempotency contracts, then implement a manually invoked bounded runner with fenced tests before enabling schedules or external events.

## Exact files changed

- Created: `docs/security/research-automation.md`
- Modified: none
