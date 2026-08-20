# E5 Interactive Research Interface — Dependency and Runtime Audit

## Scope and evidence

This audit covers the proposed E5 Interactive Research Interface and was
performed against the following read-only surfaces:

- `ROADMAP.md`, especially the E5 requirement that the CLI/report layer remains
  the analytical source of truth.
- `pyproject.toml`.
- `src/stocks_investment/cli/`.
- `src/stocks_investment/reporting/`.
- `src/stocks_investment/interfaces/`.
- `docs/architecture/`.

The current package targets Python `>=3.12`, has no runtime dependencies, and
uses `argparse`, dataclasses, JSON serialization and SQLite-backed persisted
artifacts. The CLI already exposes read-only historical inspection commands,
including thesis, changes, watchlists, strategy comparison and factor
efficacy. Reporting already has structured `ResearchReport`/`ReportSection`
objects with JSON and Markdown renderers. Interfaces are provider-independent
protocols; presentation code is not the place for financial calculations.

This document is a dependency/runtime recommendation only. It does not add a
dependency or implementation.

## Recommendation

### E5 V1: stdlib-only local research interface

Keep the runtime dependency set empty for the first E5 implementation. Extend
the existing CLI and structured reporting boundary as the primary interface.

Recommended baseline:

1. `argparse` for command parsing and exit behavior.
2. Existing typed domain/report objects as the application boundary.
3. Deterministic JSON as the machine-readable contract.
4. Existing Markdown/text renderers for human inspection and export.
5. SQLite read access through the existing storage facade.
6. Optional `cmd`-style interactive shell only if repeated exploratory use
   demonstrates a real need; it should call the same application services.

This is the smallest supported architecture that can expose historical
research without creating a second analytical runtime. It works offline,
preserves reproducibility, keeps packaging simple, and avoids committing the
project to a web or TUI framework before the user workflow is known.

### Architecture boundary

The E5 presentation flow should remain:

```text
SQLite / persisted artifacts
          |
          v
provider-free application/read services
          |
          v
ResearchReport / ReportSection / typed result objects
          |
          +--> text
          +--> JSON
          +--> Markdown
          +--> optional future HTTP/TUI adapter
```

The future adapter must consume the same service and report contracts. It must
not query providers, calculate ratios, reconstruct historical runs, or invent
classification state in a frontend.

## Alternatives evaluated

| Option | Assessment | Decision |
|---|---|---|
| `argparse` / current CLI | Built-in, Python 3.12-compatible, offline, stable, adequate for the existing command surface and explicit exit errors. | **Adopt for E5 V1** |
| `cmd` | Built-in and useful for a REPL over already-loaded/persisted services, but limited ergonomics and not necessary for scripts. | **Defer; add only with demonstrated workflow demand** |
| `http.server` | Built-in but intentionally minimal; no routing, request validation, auth, structured middleware, or production security boundary. Suitable only for a narrowly scoped local development fixture. | **Reject as a user-facing API** |
| Rich | Good terminal tables, colors and tracebacks, but adds a runtime dependency and can make terminal rendering the implicit presentation contract. It does not solve persistence, API, or accessibility by itself. | **Defer; optional presentation enhancement later** |
| Textual | Rich interactive TUI model, but a substantial framework commitment with event-loop, rendering, terminal capability and testing complexity. | **Defer until a TUI is a validated product requirement** |
| FastAPI / Starlette | Strong typed HTTP foundation, OpenAPI support and test tooling; appropriate if a stable local/API contract and concurrent clients are required. It adds runtime/security maintenance and must be paired with explicit auth, bind-address and lifecycle policy. | **Defer to an API milestone; preferred future HTTP candidate** |
| Flask | Mature and small, but less contract-oriented by default and would require choosing extensions for validation, serialization and API documentation. | **Reject for the first API; reconsider only for a Flask-specific deployment constraint** |
| Server-rendered HTML | Simple, accessible when authored carefully, no frontend build chain, and can reuse report models. It still requires a server/session/security boundary and browser testing. | **Future candidate after a read-only HTTP contract is frozen** |
| Frontend build chain (Node/React/Vite/etc.) | Enables rich interaction but introduces a second language/toolchain, dependency graph, bundling, accessibility and browser-security maintenance. It risks duplicating analytical semantics. | **Reject for E5 V1; require a demonstrated UX need and API contract first** |

## Runtime and support considerations

### Python and packaging

`requires-python = ">=3.12"` is aligned with the current `pyproject.toml` and
should remain the baseline. A stdlib-only runtime keeps editable installs and
offline test execution straightforward. Optional developer tooling should
remain in the existing `dev` extra; presentation libraries must not become
transitive runtime requirements merely because a richer output is convenient.

If a future HTTP or TUI adapter is introduced:

- pin a documented compatible range rather than an unbounded major-version
  dependency;
- keep the adapter in an optional extra, for example `interface` or `api`;
- test installation from a clean environment and package build artifacts;
- keep the core package importable without the extra installed;
- record the minimum supported Python version of the selected framework;
- review release cadence, security advisories and dependency transitivity
  before adoption.

### Offline and deterministic behavior

Normal tests must not require network access, a browser, Node, or a running
server. CLI/report tests should operate on synthetic or persisted SQLite
fixtures and should fail if a provider is unexpectedly called. JSON output
must use the existing deterministic serialization approach: explicit enum/date
handling, stable field names, and sorted keys where the current renderer
supports it.

If a server is later added, an in-process ASGI test client is preferable to
network-dependent tests, but the core historical inspection tests must remain
server-independent.

### Accessibility

The current text/Markdown/JSON outputs are naturally scriptable and usable
without a graphical environment. They should remain supported even if a UI is
added. For a future browser surface, server-rendered semantic HTML is a lower
risk accessibility starting point than a client-heavy frontend: headings,
tables, labels, keyboard navigation, focus order and error messages can be
tested directly. A TUI must support non-color cues and terminal fallback; color
alone cannot encode a score, classification or warning.

Accessibility is a reason to preserve multiple output formats, not a reason to
add a UI dependency prematurely.

### Security and maintenance

The preferred E5 V1 has no listening socket, no browser-origin policy, no
session/cookie state, no exposed database endpoint and no new attack surface.
It should continue to reject normal user errors with concise messages rather
than tracebacks and retain explicit `--format` behavior.

An HTTP interface changes the threat model materially. Before enabling one,
the project must decide and test:

- loopback-only versus externally reachable binding;
- authentication and authorization, even for read-only research;
- database path and filesystem permissions;
- request size, timeout and rate limits;
- safe error serialization without paths, credentials or SQL details;
- CORS and browser-origin policy;
- secret/configuration handling;
- dependency vulnerability monitoring and upgrade policy;
- whether reports may contain private watchlist notes.

Do not use `http.server` as a shortcut around these decisions. Do not disable
TLS verification or add hidden telemetry.

## Test implications

E5 V1 should add tests at the current boundaries, without changing analytical
engines:

- command parsing, required arguments and meaningful exit codes;
- text, JSON and Markdown output for every supported report type;
- stable JSON shape and deterministic ordering for identical persisted input;
- missing ticker/run/factor/cohort error behavior;
- provider-kill-switch tests after database reopen;
- source-lineage retention in report sections;
- explicit separation of historical research from subsequent outcomes in JSON,
  Markdown and text;
- no recomputation or current-data fallback for historical commands;
- package install/build and import with no optional interface dependency.

If a TUI is later selected, add terminal-size, non-color, keyboard navigation,
screen-reader/fallback and snapshot tests. If an HTTP adapter is later
selected, add route contract tests, authentication/binding tests, malformed
input tests, security-header tests, error redaction tests and offline ASGI
integration tests. Browser end-to-end tests should be additive, not the only
coverage of historical semantics.

## Decision triggers for upgrades

### Add `cmd` only if

- users repeatedly need multi-step exploration in one process;
- command history/state provides value that shell scripts do not;
- the same report/application service remains callable without the REPL.

### Add Rich only if

- plain text is demonstrably insufficient for inspecting rankings, lineage or
  portfolio tables;
- accessibility and `NO_COLOR` behavior are specified;
- it remains an optional presentation dependency and JSON remains canonical.

### Add Textual only if

- a terminal dashboard is explicitly prioritized over browser UX;
- the project accepts an event-loop/UI testing surface;
- the screen model is a thin consumer of report/application services.

### Add FastAPI/Starlette only if

- a stable read-only HTTP contract is approved;
- multiple clients or a local web interface justify a server;
- binding/authentication/privacy rules are documented;
- the API can be tested offline and does not become a second domain layer.

### Add server-rendered HTML only if

- a browser is needed but a client build chain is not justified;
- semantic HTML and accessibility tests are part of acceptance;
- the server remains read-only and provider-free for historical reports.

### Add a frontend build chain only if

- concrete interaction requirements cannot be met by CLI or server-rendered
  pages;
- an API contract is already frozen and versioned;
- the repository accepts Node/toolchain/lockfile/CI maintenance;
- ownership prevents financial logic, PIT filtering or classifications from
  being duplicated in JavaScript/TypeScript.

## Recommended E5 sequence

1. Freeze an application/read-service boundary around persisted research and
   the existing `ResearchReport` model.
2. Complete provider-free CLI/report coverage in the current stdlib runtime.
3. Validate deterministic JSON as the automation/integration boundary.
4. Reassess actual usage and choose either a small TUI or a read-only HTTP
   adapter; do not build both speculatively.
5. If HTTP is selected, prefer a small FastAPI/Starlette adapter in an optional
   extra, with server-rendered HTML or a separate frontend considered only
   after the API contract is stable.

## Final recommendation

E5 should begin with no new runtime dependency and no browser/frontend build
chain. The current `argparse` + typed reports + deterministic JSON/Markdown
surface is sufficient to establish the interface contract while preserving
the project’s strongest guarantees: offline reproducibility, historical
immutability, source lineage and provider-free inspection.

The first upgrade trigger is not visual polish; it is a demonstrated need for
multi-user or browser consumption. At that point FastAPI/Starlette is the
most credible API candidate, with server-rendered HTML as the lowest-complexity
browser presentation. Textual/Rich and a frontend build chain remain optional
alternatives, not baseline dependencies.

## Required workstream report

WORKSTREAM: E5-D — Dependency/runtime audit
STATUS: COMPLETED

Scope completed:

- Audited `pyproject.toml`, roadmap E5 requirements, CLI/reporting contracts,
  interfaces and architecture documents.
- Compared stdlib CLI/REPL/server options, terminal UI libraries, Python web
  frameworks, server-rendered HTML and frontend build chains.
- Evaluated packaging, Python support, offline tests, deterministic JSON,
  accessibility, security maintenance and upgrade triggers.

Files created:

- `docs/audit/e5-dependency-audit.md`

Files modified:

- None outside the exclusive write fence.

Contracts consumed:

- Existing `ResearchReport`/`ReportSection` reporting boundary.
- Existing provider-independent research interfaces.
- Existing read-only CLI and SQLite persistence conventions.

Shared-contract changes requested:

- None.

Tests added/executed:

- No code or tests were added; this was a read-only dependency audit.

Results:

- Recommendation: stdlib-only E5 V1; defer HTTP/TUI/frontend dependencies.
- If an HTTP milestone is approved later, FastAPI/Starlette is the preferred
  candidate subject to a separate security and API contract gate.

Assumptions:

- E5 remains an inspectability/interface layer and does not change analytical
  truth or historical persistence semantics.
- Existing CLI/report output contracts remain the canonical edge boundary.

Known limitations:

- No live performance or accessibility benchmark was run because no UI/API
  implementation is in scope.
- Framework versions were not pinned because no dependency is recommended for
  the current milestone.

Recommended next action:

- Chief Architect should freeze the E5 application/read-service boundary, then
  implement provider-free CLI/report improvements under directory ownership.
- Re-open dependency selection only when a concrete TUI or HTTP use case and
  its security/acceptance criteria are approved.
