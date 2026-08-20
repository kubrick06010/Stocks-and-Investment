# E3 — Dependency Audit

## Scope and conclusion

This audit maps the existing persisted path for the E3 automation objective:

```text
new filing
  -> filing evidence / claims
  -> normalized observations and a ResearchRun
  -> persisted ResearchResult
  -> persisted ThesisSnapshot
  -> persisted ResearchChangeEvent
  -> WatchlistEntry / MonitoringEvent
  -> ResearchReport / CLI
```

The repository already contains the analytical and persistence primitives for
each downstream artifact. The missing capability is a small, deterministic,
idempotent orchestration boundary that coordinates those primitives. E3 should
not duplicate screening, thesis generation, change detection, watchlist
evaluation, filing parsing, or report construction.

The recommended dependency direction is:

```text
SecFilingsProvider / other providers
  -> SafeFilingParser
  -> claims / filing history
  -> persisted filing evidence
  -> existing observation + screening pipeline
  -> StructuredThesisEngine
  -> compare_results
  -> evaluate_watchlist
  -> build_historical_stock_report / filing reports
```

E3 should provide only orchestration, run identity/idempotency, trigger
selection, step status, and failure reporting around this path.

## Existing components and exact reuse points

### Filing acquisition and evidence

* `src/stocks_investment/data/providers/sec_filings.py::SecFilingsProvider`
  exposes `filings(ticker, as_of)` and `content(filing)`. It already applies
  SEC user-agent, HTTPS, timeout/retry, and availability filtering. E3 should
  call the provider through its existing interface and should never read
  `filings.recent` or provider payloads directly.
* `src/stocks_investment/domain/filings.py` contains the immutable records
  `FilingDocument`, `FilingSection`, `FilingEvidenceReference`,
  `QualitativeClaim`, and `FilingEvidenceSnapshot`. `FilingDocument` keeps
  `filed_at`, `available_at`, `retrieved_at`, and `period_end` separate. E3
  must use `available_at` as the historical availability boundary.
* `src/stocks_investment/filings/parser.py::SafeFilingParser.parse` converts
  provider bytes into bounded, inert `FilingSection` records. It has no
  provider dependency and is the only parser E3 should invoke.
* `src/stocks_investment/filings/claims.py::build_disclosed_risk_claims` and
  `build_analyst_authored_claim` create evidence-backed qualitative claims.
  E3 may invoke the deterministic disclosed-risk path when configured; it
  must not invent unsupported claims or free-form business conclusions.
* `src/stocks_investment/filings/history.py::compare_filing_sections` and
  `FilingHistoryComparator.compare` compare filings by `(item, kind)` identity,
  not ordinal position. E3 should reuse this for filing-change artifacts and
  must not implement a second diff algorithm.

### Persistence and PIT access

`src/stocks_investment/storage/sqlite.py::SQLiteStorage` is the current
coherent persistence facade. It already persists the needed Wave B–D records:

* `save_filing_document`, `load_filing_document`, and
  `load_filings_available_on` for filing identity and PIT filtering;
* `save_filing_section`, `load_filing_sections`;
* `save_qualitative_claim`, `load_qualitative_claims`;
* `save_filing_section_change`, `load_filing_section_changes`;
* `save_filing_evidence_snapshot`, `load_filing_evidence_snapshot`;
* `save_observation`, `load_observations`, and `attach_observation`;
* `save_research_run`, `load_research_run`;
* `save_research_result`, `load_research_result`, and
  `load_research_results`;
* `save_thesis_snapshot`, `load_thesis_snapshot`,
  `load_thesis_snapshots`;
* `save_change_event`, `load_change_events`;
* `save_watchlist_entry`, `load_watchlist_entry`,
  `load_watchlist_entries`;
* `save_monitoring_event`, `load_monitoring_events`;
* `save_research_outcome`, `load_research_outcomes`; and
* `save_backtest_run`, `load_backtest_run`, and `load_backtest_runs`.

The storage facade also has the E1 statistical and E2 filing migration state.
E3 should reuse this facade and add no provider-specific storage path. A
future migration may add automation-run records, but existing research and
filing tables should remain unchanged.

The current storage methods are mostly write-through and commit immediately.
An E3 run therefore needs an explicit run/idempotency record to distinguish a
completed step from a partially completed sequence. It should not infer this
from the presence of a single downstream object.

### Research creation and persistence

`src/stocks_investment/screening/engine.py::ScreeningEngine.screen` is the
existing construction path for a versioned `ResearchRun` and its
`ResearchResult` records. It accepts a `UniverseSnapshot`, candidates,
strategy identity/version, `MissingDataPolicy`, data snapshot, and persistence
flag. Its `_persist` method saves the universe, run, and results.

This is the critical reuse point for E3. Automation must prepare normalized,
PIT-valid candidates and invoke this existing engine. It must not construct a
second ResearchRun algorithm, rerun strategies in a scheduler, or copy its
ranking logic.

The canonical records are:

* `domain/research.py::ResearchRun`, including `strategy_name`,
  `strategy_version`, `as_of`, universe identity, parameters, data snapshot,
  and status;
* `domain/research.py::ResearchResult`, including rank, composite score,
  classification, factor scores, criteria, and source observation IDs; and
* `domain/research_engine.py::UniverseSnapshot`,
  `FactorObservation`, `FactorScore`, `CriterionResult`, and the PIT
  `PointInTimeDataView`.

E3 must preserve strategy and universe versions in every automation request.
If source filings cause an observation refresh, that is an input/data refresh
to a new ResearchRun, not an in-place update to a historical run.

### Thesis, history, watchlist, and reporting

* `src/stocks_investment/thesis/engine.py::StructuredThesisEngine.generate`
  consumes one persisted-compatible `ResearchRun` and `ResearchResult`, and
  returns a deterministic `ThesisSnapshot` with version
  `structured_thesis_v1`. It performs no provider access. E3 should invoke it
  once per result requiring a thesis snapshot and persist the result with
  `save_thesis_snapshot`.
* `src/stocks_investment/history/changes.py::compare_results` compares an
  earlier and later `ResearchResult` plus a versioned `MaterialityPolicy`.
  It verifies run/result and ticker identity. E3 should load the prior
  persisted run/result and call this function; it must not rebuild the prior
  state from current inputs.
* `src/stocks_investment/watchlist/engine.py::evaluate_watchlist` evaluates a
  `WatchlistEntry` against a new `ResearchRun` and matching `ResearchResult`.
  It returns `MonitoringEvent` values and uses criterion observed values for
  numeric conditions. E3 should load existing entries, pass the new result,
  and persist returned events. It must not inspect later outcomes to trigger a
  watch condition.
* `src/stocks_investment/reporting/builder.py::build_historical_stock_report`
  assembles persisted thesis snapshots, change events, watchlist entries,
  monitoring events, and outcomes into a `ResearchReport`. Its section types
  distinguish `research` from `outcome`. E3 should pass loaded artifacts to
  this builder after the run is complete; it should not add report-specific
  analytical calculations.
* `src/stocks_investment/reporting/filings.py` provides
  `build_filing_evidence_report` and `build_filing_history_report`. These are
  suitable for a filing-triggered evidence report and preserve evidence,
  interpretation, and history boundaries.

The CLI in `src/stocks_investment/cli/__init__.py` already reads persisted
history for `thesis`, `thesis-history`, `changes`, `watchlist`,
`compare-strategies`, `factor-efficacy`, `report`, `filings`, and
`filing-history`. E3 should invoke services behind the same persisted state;
it should not make CLI commands a second orchestration implementation.

## Precise reusable E3 path

The minimum E3 execution can be represented as the following steps. Each step
must carry a stable automation-run ID and an idempotency key.

1. **Detect:** call `SecFilingsProvider.filings(ticker, as_of)` or consume a
   persisted provider event. Compare filing IDs/content hashes with
   `load_filings_available_on`. A new filing is identified by stable filing
   identity/content, not by wall-clock polling alone.
2. **Persist evidence:** call `content`, then `SafeFilingParser.parse`, the
   configured claim builder, `FilingHistoryComparator` when a previous filing
   exists, and the corresponding `SQLiteStorage.save_*` methods. Reject a
   filing not available at the run as-of date.
3. **Refresh observations:** convert the newly available filing/normalized
   financial inputs through the existing observation/metric pipeline. Use
   `save_observation` and retain IDs. This is the one place where E3 needs an
   explicit existing provider/metric adapter contract; E3 must not calculate
   ratios itself.
4. **Create research:** construct the same candidate structures accepted by
   `ScreeningEngine.screen`, pass the exact `UniverseSnapshot`, strategy name,
   version, parameters, data snapshot, and `as_of`, then persist the returned
   run/results through the engine.
5. **Generate thesis:** load the just-persisted run/results and call
   `StructuredThesisEngine.generate`; persist immutable snapshots. Never
   overwrite an older snapshot with a newer methodology version.
6. **Detect changes:** for each ticker with an earlier comparable result, load
   both persisted runs/results and call `compare_results` with the configured
   `MaterialityPolicy`; persist each event. This step consumes research state,
   not outcomes.
7. **Evaluate watchlists:** load `WatchlistEntry` records, match entries to
   the new results by ticker, call `evaluate_watchlist`, and persist
   `MonitoringEvent` values. State transition/deduplication remains keyed by
   entry and research run.
8. **Report:** load the persisted artifacts and call the existing report
   builders. Reports can include later outcomes only in the explicit outcome
   section. A provider-free report read-back must work after DB reopen.

The order is intentional: source evidence and observations precede research;
research precedes thesis/change/watchlist; reporting is last. E3 should expose
step-level status rather than hide failures behind one broad exception.

## Missing contracts and minimal additions

### 1. Automation run identity and idempotency — required

No current domain record represents an orchestration execution. Add one small
E3 contract, for example `AutomationRun`, with:

* `id`, `created_at`, `as_of`, trigger type/source;
* requested tickers/universe and strategy/version;
* deterministic `idempotency_key`;
* status (`created`, `running`, `completed`, `failed`, `partial`);
* data snapshot and optional git commit;
* per-step status/error references.

Persisting this record is the minimal way to make retries safe and explain a
partial run. Do not create one storage protocol per step.

### 2. Orchestration seam — required

The existing provider, screening, thesis, history, watchlist, and reporting
interfaces are separate. There is no interface that coordinates them. Add a
small provider-independent `ResearchAutomationRunner`/`AutomationPipeline`
interface accepting explicit dependencies and a clock. It should return a
structured run result and never own metric or strategy logic.

Required properties:

* deterministic dependency injection;
* explicit `as_of` and data snapshot;
* step-level outcomes;
* idempotent replay behavior;
* no hidden current-data fallback;
* no background daemon requirement for V1.

### 3. Filing-to-observation adapter — likely required

E2 persists filing evidence but does not produce the normalized financial
observations consumed by `ScreeningEngine`. The audit found no existing
filing-to-fundamental adapter in the repository. This is a real boundary, but
it belongs to the data/fundamentals contract, not to automation logic.

E3 should depend on a narrow adapter such as `FilingObservationSource` or an
existing future fundamental provider that returns canonical observations with
PIT provenance. Do not place EPS, revenue, or ratio formulas in E3.

### 4. Trigger/schedule representation — required for scheduling only

No reusable schedule/job contract is visible in the current tree. For V1,
represent triggers as explicit request records (`new_filing`, `manual`,
`scheduled`) and use an injected clock. A cron/launchd/CI adapter can call the
runner later. Do not introduce a daemon or scheduler framework before the
pipeline is proven.

### 5. Step failure and retry semantics — required

Existing storage commits each object independently. E3 needs an explicit
policy for partial completion: retry only failed idempotent steps, retain
successful evidence, and never overwrite immutable historical artifacts.
The policy should distinguish transient provider failure from invalid data or
PIT rejection.

### 6. Optional material-change report trigger — derived, not a new engine

Material change detection already exists in `compare_results`. E3 can request
report generation when returned events meet configured materiality, but should
not create another materiality implementation. A simple run parameter or
trigger policy is sufficient.

## What is already sufficient

The following should not be redesigned for E3:

* `SQLiteStorage` as the single persistence facade;
* `FilingDocument` availability semantics;
* `SafeFilingParser` and its fail-closed active-markup handling;
* `FilingHistoryComparator` identity-safe comparison;
* `ScreeningEngine.screen` as the ResearchRun/Result persistence path;
* `StructuredThesisEngine` as deterministic thesis generation;
* `compare_results` as historical state comparison;
* `evaluate_watchlist` as new-ResearchRun monitoring;
* `build_historical_stock_report` and filing report builders;
* the existing CLI as a read-only historical presentation edge.

Duplicating any of these in an automation module would create a second
research engine and make historical results diverge.

## Information-barrier and reproducibility requirements

E3 must preserve these boundaries:

* A filing is usable only when `FilingDocument.is_available_on(as_of)` is
  true. `period_end`, `filed_at`, `available_at`, and `retrieved_at` remain
  separate.
* A new run is a new immutable `ResearchRun`; an automation retry must not
  mutate an earlier run or thesis snapshot.
* Change detection receives two persisted research states and never receives
  `ResearchOutcome` values.
* Watchlist evaluation receives the new persisted research result and never
  uses future outcomes.
* Outcome data can be added after the decision and rendered in the separate
  report outcome section.
* Provider-free close/reopen inspection must be a required E3 integration
  test.
* Strategy version, universe version, factor versions, data snapshot, and
  automation idempotency key must remain inspectable.

## Suggested minimal dependency graph

```text
AutomationRun / request
        |
        v
  provider + clock
        |
        v
  filing evidence persistence
        |
        v
  canonical observations / ScreeningEngine
        |
        v
  ResearchRun + ResearchResult
       /|\
      / | \
     v  v  v
 thesis changes watchlist
      \  |  /
       \ | /
        v v v
      report builders
```

All arrows are dependency-injected calls. No arrow should point from a report,
outcome, or watchlist back into historical research computation.

## Risks and explicit non-goals

* **Filing-to-fundamental gap:** E2 evidence is not automatically a complete
  financial-statement observation source. E3 must fail honestly or mark
  insufficient data when canonical inputs are unavailable.
* **SEC history coverage:** the current SEC adapter focuses on recent
  submissions and does not itself provide a complete historical filing
  archive. Automation must not imply full historical coverage.
* **Atomicity:** SQLite methods commit per operation. Automation status and
  idempotency are needed to recover from partial runs; a large transaction
  refactor is not justified by this audit.
* **Scheduling:** a scheduler/daemon is not required for the first vertical
  slice. A manual/CI invocation with an injected clock is safer and easier to
  reproduce.
* **No qualitative thesis inference:** filing claims remain evidence-first;
  E3 must not convert lexical disclosure presence into unsupported investment
  conclusions.
* **No new scoring or strategy:** E3 orchestrates validated strategies and
  metrics; it does not add factors, formulas, or optimization.

## Recommended implementation ownership fence

If E3 is implemented in parallel, use separate non-overlapping workstreams:

* **E3 contracts:** `src/stocks_investment/domain/automation.py`,
  `src/stocks_investment/interfaces/automation.py`, and architecture/decision
  docs only after lead approval.
* **E3 runner:** `src/stocks_investment/automation/` and its tests; may call
  existing public services but may not modify them.
* **E3 persistence:** storage migration and storage tests only; no runner or
  analytical module edits.
* **E3 integration:** `tests/e2e/` and validation docs only; must use the
  shared fixture and provider guards.

Any contract insufficiency must be raised as a change request before touching
`domain/`, `interfaces/`, or existing analytical implementations. The current
Git sandbox cannot provide branch/worktree isolation, so these logical fences
are the required safety mechanism.

## Required agent report

WORKSTREAM: E3-DEPENDENCY-AUDIT
STATUS: COMPLETE — audit only; no production implementation performed
Scope completed: mapped filing → observation → ResearchRun → thesis → changes → watchlist → report reuse path and identified minimal missing contracts.
Files created: `docs/audit/e3-dependency-audit.md`
Files modified: none
Contracts consumed: filing domain records; SQLiteStorage; ScreeningEngine; StructuredThesisEngine; compare_results; evaluate_watchlist; report builders; existing CLI.
Tests added: none, per ownership fence.
Tests executed: read-only source inspection only; no test suite changes or execution required for this audit.
Results: existing downstream path is reusable; E3 needs an automation-run/idempotency record, orchestration seam, filing-to-observation adapter boundary, trigger representation, and retry policy.
Assumptions: E3 uses the existing SQLite facade and validated analytical services; filing evidence alone is not treated as complete normalized financial data.
Known limitations: no live provider execution was performed; SEC historical coverage and filing-to-observation conversion remain explicit dependencies.
Dependencies on other workstreams: data/fundamental observation provider contract; existing screening, thesis, history, watchlist, reporting, and storage implementations.
Recommended next action: freeze the minimal E3 automation contracts, then implement one manual/injected-clock vertical slice with idempotent retries before adding scheduling.

## Exact files changed

`docs/audit/e3-dependency-audit.md` only.
