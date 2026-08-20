# E5-R — Interactive Research Interface Recommendation

## Scope and architectural premise

This document is a design recommendation only. It is based on `ROADMAP.md`, the
validated Wave B–E4 artifacts, the existing CLI, reporting builders, domain
records, interfaces, and `SQLiteStorage`.

The interface is an inspection surface for persisted research. It is not a new
research engine. The existing services remain authoritative for calculations,
point-in-time selection, thesis generation, comparison, factor efficacy,
watchlists, portfolio construction, and reporting.

The non-negotiable flow is:

```text
SQLiteStorage / provider-free repositories
              ↓
validated domain and reporting services
              ↓
structured ResearchReport / domain results
              ↓
interactive presentation
```

An interface must never turn a historical lookup into a new provider request or
recompute a historical result with current data.

## Existing capabilities to reuse

The repository already provides the important seams required by E5:

- `stocks_investment.cli` exposes read-only commands for thesis, thesis history,
  changes, watchlists, strategy comparison, factor efficacy, reports, filings,
  and automation inspection.
- `stocks_investment.reporting` builds structured `ResearchReport` objects and
  renders JSON and Markdown.
- `ReportSection.section_type` already distinguishes research sections from
  subsequent outcome sections.
- `SourceReference`, `ResearchRun`, `ResearchResult`, `ThesisSnapshot`,
  `ResearchChangeEvent`, `FactorOutcomeObservation`, `BacktestRun`, and
  `UniverseSnapshot` provide stable historical lineage.
- `SQLiteStorage` is the local persistence boundary and supports close/reopen
  inspection without requiring a provider.
- `interfaces/` contains provider-independent service contracts. The UI should
  depend on those services or read-only application adapters, never on provider
  payloads.
- `pyproject.toml` has no runtime dependencies. This is valuable for a local,
  reproducible research tool and should not be discarded for a first interface.

The current CLI has a deliberately simple argument model and already supports
`text`, `json`, and `markdown`. E5 should preserve those command semantics and
factor interactive access through the same read-only application layer rather
than importing CLI internals into a web frontend.

## Options considered

### Option A — terminal interactive shell / TUI

Examples include a command loop or a curses-style screen that invokes existing
read-only application services.

Strengths:

- Smallest implementation and dependency footprint; a command loop can use the
  standard library.
- Naturally compatible with the existing `stocks` CLI and local SQLite path.
- Easy to keep provider-free: every action can be a read-only query against a
  reopened database.
- Good fit for researchers who already work in a terminal and for SSH/headless
  environments.
- Easy to make deterministic: command plus database snapshot produces a stable
  result.

Tradeoffs:

- Weak discoverability for timelines, lineage graphs, and side-by-side strategy
  comparison.
- Terminal capability, color, screen-reader, and keyboard behavior require
  careful handling. A curses dependency would increase portability risk.
- Less suitable for sharing a research report with another person.

### Option B — local read-only HTTP API

A loopback-only HTTP service exposing query/report endpoints, with no mutation or
provider routes.

Strengths:

- Clean separation between query services and presentation clients.
- Supports a future TUI, local server-rendered UI, or external tooling without
  duplicating analytics.
- HTTP responses can carry structured lineage, status, version, cohort, and
  information-boundary metadata directly.
- The standard library can provide a minimal implementation; no framework is
  required for V1.
- A read-only API makes provider-free and deterministic behavior testable at one
  boundary.

Tradeoffs:

- Adds a process and an API lifecycle to a currently synchronous CLI.
- Requires explicit security controls even on loopback: bind address, request
  limits, path validation, and no accidental network/provider routes.
- An API alone is not a pleasant end-user interface.

### Option C — server-rendered local UI

A loopback-only HTTP server that renders HTML from the same structured reports,
with ordinary links and forms for read-only navigation.

Strengths:

- Best value for historical timelines, source lineage, research/outcome
  separation, watchlists, and strategy comparison.
- Server-rendered HTML is accessible by default when semantic headings, tables,
  links, keyboard navigation, and text alternatives are used.
- No frontend build toolchain, JavaScript analytics, or SPA state cache is
  required.
- The same report data can be rendered as text, JSON, Markdown, or HTML.
- Works locally and can remain provider-free after opening the database.

Tradeoffs:

- Requires a small HTML renderer and a local server lifecycle.
- HTML escaping, URL/query validation, and explicit content boundaries become
  security responsibilities.
- Interactive filtering is less fluid than a SPA, although this is acceptable
  for a research inspection tool.

### Option D — SPA / web dashboard

A browser application with a JavaScript/TypeScript frontend and a local API or
backend.

Strengths:

- Strongest interaction model for dense charts, linked timelines, drill-down,
  multi-panel comparisons, and future collaborative presentation.
- Can provide rich client-side navigation after one data load.

Tradeoffs:

- Largest dependency, packaging, and maintenance surface by far.
- High risk of duplicating domain semantics in frontend code: date filtering,
  rankings, factor normalization, outcome sections, or version selection could
  drift from the validated Python services.
- Client-side caching can accidentally mix research-as-of data with later
  outcomes or current data unless every payload carries and every view enforces
  boundary metadata.
- Accessibility, browser compatibility, build reproducibility, and security are
  substantially more demanding.
- It solves presentation scale before the repository has evidence that a
  dashboard is the highest-value missing capability.

## Recommendation

Recommend a staged V1 composed of:

1. A small read-only application/query facade over existing services and
   `SQLiteStorage`.
2. A loopback-only standard-library HTTP API for stable structured queries.
3. A server-rendered HTML interface using the same query results and report
   sections.
4. The existing CLI remains the scriptable and machine-oriented surface.

This is intentionally not a SPA. The API and server-rendered UI share a single
read-only query layer, so the repository gains an interactive interface without
creating a second analytical implementation. A minimal terminal command loop is
an optional convenience built on the same facade; a full TUI is not required for
V1.

### Proposed V1 surface

The first useful navigation set should be small:

- `/` — database status, available research dates, and a link to recent runs.
- `/stock/<ticker>` — current persisted research state, thesis, factors,
  criteria, source lineage, and clearly separated subsequent outcomes.
- `/stock/<ticker>/history` — thesis snapshots and material changes keyed by
  date and ResearchRun.
- `/screen/<run-id>` — persisted ranking, factor decomposition, criteria, and
  universe identity.
- `/compare/<backtest-a>/<backtest-b>` — agreement and, only when compatible,
  persisted performance comparison with mismatch metadata otherwise.
- `/factor/<factor-version>?horizon=12M` — persisted factor efficacy, cohort,
  coverage, limitations, and outcome horizon.
- `/watchlist` — entries, reasons, conditions, and monitoring events.
- `/reports/<kind>` — the existing structured report rendered for humans.

The exact URL spelling is provisional. The important contract is that every
response identifies its source runs, versions, as-of date, cohort or benchmark
where relevant, and whether a section is `research` or `outcome`.

### Query behavior

Queries should be deterministic and read-only:

- Open the configured SQLite database in read-only mode where supported.
- Resolve identifiers explicitly; do not infer “latest” across incompatible
  strategy, thesis, factor, universe, benchmark, or horizon versions.
- Return an explicit empty, missing, incompatible, or insufficient-data state.
- Preserve ticker and date identity by keying all joins on stable identifiers,
  never row position.
- Never call market, fundamental, universe, benchmark, filing, or automation
  providers during historical inspection.
- Never mutate a ResearchRun, ThesisSnapshot, BacktestRun, WatchlistEntry, or
  derived historical evidence object from a GET/query operation.

## Information barriers and lineage

The interface must make the information boundary visible in both data and
presentation.

Every response should carry or expose:

- `as_of` and the relevant `ResearchRun` identity;
- strategy name and version;
- thesis/factor version where applicable;
- universe snapshot or cohort identity;
- benchmark and outcome horizon for performance/effectiveness;
- `source_references` back to persisted artifacts;
- section type: `research`, `outcome`, or another explicitly defined class.

Historical research belongs in a “Research as of …” region. Later performance
belongs in a separate “Subsequent outcome” region. The separation must survive
JSON, HTML, Markdown, and terminal output. A future `+500%` outcome must never be
rendered inside a historical thesis summary, driver list, classification, or
watch condition.

The interface should expose a lineage path such as:

```text
report section
  -> ThesisSnapshot / ChangeEvent / WatchlistEntry / FactorEfficacySummary
  -> ResearchResult / OutcomeObservation / BacktestRun
  -> ResearchRun + UniverseSnapshot
  -> FactorScore / CriterionResult / MetricObservation
  -> DataProvenance
```

Links should be stable local references or identifiers, not provider URLs that
would silently fetch current information.

## Accessibility and presentation requirements

The recommended server-rendered UI should be accessible without JavaScript:

- semantic headings and landmarks;
- real table headers for rankings and comparisons;
- keyboard-operable links and controls;
- visible focus states and sufficient color contrast;
- status conveyed by text, not color alone;
- expandable detail represented with ordinary links or native disclosure where
  supported;
- no essential information hidden in charts only;
- text alternatives for timelines and score decompositions;
- responsive layout that remains usable at narrow widths;
- a plain-text/CLI equivalent for every important inspection action.

Charts are optional. If introduced later, their underlying tabular data and
lineage must remain available in the response.

## Explicit non-goals for E5 V1

- No live trading, broker integration, order submission, or portfolio mutation.
- No provider refresh, background polling, websocket, notification daemon, or
  hidden network request.
- No financial calculation, ranking, strategy evaluation, backtest, factor
  efficacy calculation, or thesis regeneration in HTML, JavaScript, or route
  handlers.
- No SPA build pipeline, frontend framework, client-side analytics engine, or
  duplicated domain model.
- No authentication system or multi-user collaboration in a local-only V1.
- No LLM, narrative generation, sentiment, or recommendation language.
- No arbitrary SQL endpoint, filesystem browser, or user-supplied code execution.
- No mutation endpoints for watchlists or research state until a separate
  authorization and audit design exists.

## Suggested implementation boundary

The smallest coherent implementation would introduce a read-only application
facade, for example `ResearchQueryService`, as an implementation detail of a
future E5 contract freeze. It would accept an opened storage facade and frozen
service dependencies, and return existing domain/report objects or small typed
view models. It should not own calculations.

The HTTP layer should use only the Python standard library in V1 (`http.server`,
`urllib.parse`, `html`, `json`, and `sqlite3` through the storage boundary). A
small renderer can escape all dynamic text and render tables from structured
sections. The CLI can call the same facade, or retain its current direct
read-only orchestration until that facade is introduced deliberately.

Read-only enforcement should include:

- a separate read-only storage constructor or SQLite URI mode;
- an allowlist of query routes;
- no POST/PUT/PATCH/DELETE routes in V1;
- provider-kill-switch tests around every route;
- tests that mutate storage after the UI has loaded later data and verify old
  historical objects are unchanged;
- stable JSON serialization with sorted keys and explicit enum/date encoding.

The API should bind to loopback by default and print the chosen address/port
explicitly. It should not claim to be safe for exposure on a LAN or the public
internet.

## User journeys

### Explain one historical decision

1. User opens `AAA`.
2. UI shows the selected persisted ResearchRun and `as_of` date.
3. User sees classification, factor scores, Graham criteria, and thesis drivers.
4. Each section links to its source references and version identities.
5. A separate section shows later outcomes, if requested, without changing the
   historical interpretation.

### Understand what changed

1. User opens the stock history.
2. UI lists snapshots chronologically by date and ResearchRun.
3. Material changes show old value, new value, status transitions, and source
   references.
4. A rank change is keyed to the ticker, not to a positional row.

### Compare strategies honestly

1. User selects two persisted backtests.
2. UI shows strategy name/version and all compatibility assumptions.
3. Agreement metrics render when valid.
4. Performance renders only for compatible simulations; otherwise exact mismatch
   reasons are shown and no winner is declared.

### Inspect factor efficacy

1. User selects factor version, horizon, universe/cohort, and benchmark.
2. UI shows eligible/usable observations, coverage, quantile behavior, rank IC,
   hit rate, and scientific limitations.
3. Mixed versions, horizons, universes, currencies, or benchmarks are rejected
   or split explicitly.

### Review a watchlist

1. User opens the watchlist.
2. UI shows the reason for each entry, source run, conditions, current state,
   and monitoring history.
3. A trigger links to the ResearchRun that changed the condition.
4. No outcome is used to trigger a watch condition.

## Acceptance criteria

### Functional

- The V1 interface exposes stock history, persisted runs, strategy comparison,
  factor efficacy, watchlists, and reports through the same read-only query
  services.
- Every historical result is inspectable after closing and reopening the
  database.
- JSON, HTML, Markdown, and terminal output retain source references and
  version/cohort metadata.
- Missing, empty, insufficient, and incompatible queries have typed user-facing
  states and no traceback.
- Performance comparison never presents incompatible BacktestRuns as a direct
  winner.

### Scientific integrity

- Provider kill-switch tests cover all interface routes and report builders.
- T4/future-data attacks prove that old thesis, changes, rankings, watch states,
  and factor inputs remain unchanged.
- A later outcome appears only in outcome sections.
- Repeated queries against the same reopened database have identical semantic
  results and stable JSON payloads apart from explicitly allowed metadata.
- Security, date, strategy, factor, thesis, universe, benchmark, horizon, and
  source identities are preserved through every view.

### Accessibility and security

- All core workflows work without JavaScript.
- Keyboard navigation, headings, table semantics, text alternatives, and
  non-color status are tested manually and with lightweight checks.
- Dynamic HTML is escaped; URLs and identifiers are validated.
- The server binds to loopback, has no mutation routes, no arbitrary SQL, and no
  provider/network fallback.
- The package remains installable without a runtime frontend dependency.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| UI accidentally recalculates history | Query facade accepts persisted artifacts and has provider-kill-switch tests. |
| Research and outcome contamination | Typed section type plus separate JSON/HTML regions and adversarial tests. |
| “Latest” silently mixes versions | Require explicit identifiers; report insufficient/incompatible state. |
| Local HTTP exposure | Loopback default, no auth claim, no mutation routes, explicit warning. |
| HTML injection through notes or provider data | Escape all dynamic text and never render raw HTML payloads. |
| Accessibility regression | Server-rendered semantic HTML, keyboard-only checks, text alternatives. |
| API becomes a second domain model | Return existing reports/domain objects; keep only narrow view models at the edge. |
| Dependency drift | Standard library V1; no frontend build or chart dependency. |
| Large databases make pages slow | Paginate or narrow queries deterministically; never add hidden live refresh. |
| Future SPA pressures architecture | Keep API/schema provider-independent and report-oriented, but defer SPA until measured need. |

## Dependencies and sequencing

E5 should begin with a small contract freeze for the read-only query facade and
route payloads. It depends on the validated E1–E4 artifacts but should not edit
their analytical contracts.

Suggested ownership after that freeze:

- `e5-query`: read-only application facade and typed query/view models;
- `e5-http`: loopback HTTP adapter and route tests;
- `e5-rendering`: HTML/text/JSON presentation adapters;
- `e5-cli`: CLI wiring only, with no analytical changes;
- `e5-adversarial`: provider kill switch, information barrier, determinism,
  accessibility, and injection tests.

Fences should be directory-based because Git branch/worktree isolation is not
available in the current sandbox. No agent should edit `domain/`, `interfaces/`,
`storage/`, or existing analytical packages without a centrally approved
contract change.

## Decision

Adopt a local, read-only, server-rendered interface backed by a minimal
standard-library HTTP query surface and the existing CLI/reporting services.
Treat a terminal command loop as an optional second adapter. Defer a full TUI,
SPA, public server, authentication, and collaboration until actual usage shows
that the V1 surface cannot answer historical research questions efficiently.

This recommendation maximizes research integrity and accessibility per unit of
new code: the interface makes persisted evidence easier to inspect while
preserving the project's defining property that the past is immutable and the
future may evaluate it but may not rewrite it.

## Required workstream report

WORKSTREAM: E5-R — Interactive Research Interface Architecture

STATUS: COMPLETED — recommendation only; no implementation performed

Scope completed:

- Compared terminal shell/TUI, local read-only HTTP API, server-rendered local
  UI, and SPA/web dashboard.
- Recommended a minimal local read-only HTTP + server-rendered V1 backed by the
  existing CLI/reporting and storage services.
- Defined explicit non-goals, user journeys, acceptance criteria, risks,
  dependencies, information-barrier requirements, and ownership boundaries.

Files created:

- `docs/research/interactive-research-interface.md`

Files modified:

- None outside the exclusive write fence.

Tests added/executed:

- None; this workstream is architecture research only.

Contracts consumed:

- Existing CLI, reporting, domain, interface, storage, and roadmap contracts.

Shared-contract changes requested:

- None. A future E5.0 freeze should define a narrow read-only query facade and
  route payloads before implementation.

Known limitations:

- No usability study or browser accessibility audit has been performed.
- No production HTTP adapter has been implemented or benchmarked.
- The recommendation assumes local single-user inspection remains the primary
  near-term use case.

Recommended next action:

- Review this recommendation, then freeze the E5 query-facade and local-server
  contracts before implementation. Keep the initial implementation narrow and
  provider-free.
