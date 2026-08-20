# E5-S — Interactive Research Interface Threat Model

Status: security/privacy design review
Scope: a local, read-mostly interface over persisted SQLite research history
Owner: E5-S security/privacy review
Date: 2026-08-19

This document is a threat model and release checklist. It does not authorize an
HTTP server, a browser UI, provider access, telemetry, or a new persistence
surface. The existing CLI and reporting layer remain the analytical source of
truth; an interface may only read and render their structured outputs.

## Security objectives

The interface must:

1. open only the database explicitly selected by the user or a documented,
   safe local default;
2. remain local-only by default, with no provider fallback and no background
   network activity;
3. preserve the distinction between research known at `as_of` and later
   outcomes in every representation;
4. render untrusted stored strings as data, never executable markup or code;
5. preserve source lineage and stable identifiers without exposing unrelated
   local files or secrets;
6. fail closed on malformed paths, records, filters, and unsupported formats;
7. avoid browser or HTTP behavior that expands access beyond the local user;
8. remain bounded and deterministic under large or adversarially populated
   databases.

## Assets

| Asset | Security/privacy property | Consequence of loss or corruption |
|---|---|---|
| SQLite research database | confidentiality, integrity, historical immutability | disclosure of private research; false historical conclusions |
| ResearchRun, Result, scores, criteria | authenticity and lineage | inability to explain or reproduce decisions |
| Thesis and change history | integrity and temporal separation | rewritten history or misleading investment narrative |
| FactorOutcomeObservation and outcomes | integrity and information-boundary separation | look-ahead contamination or false efficacy claims |
| User-authored watch notes/tags | confidentiality, integrity, availability | private commentary disclosure or stored-content injection |
| Database path/configuration | confidentiality and user intent | arbitrary local-file reads or wrong-database analysis |
| Source URLs and filing metadata | integrity and safe display | phishing, tracking, or external-navigation surprises |
| CLI/report output | integrity and safe serialization | terminal/UI injection or machine-readable corruption |
| Process/network boundary | least privilege | unintended LAN exposure, provider access, or telemetry |

## Assumptions and trust boundaries

### Current evidence

- The CLI requires `--db` for historical commands and uses `SQLiteStorage`.
- `SQLiteStorage` expands a supplied path and creates its parent directory;
  database selection is therefore security-sensitive and must be validated at
  the interface edge.
- SQLite queries observed in the storage layer use parameter binding for
  application values. This is a required invariant, not permission to build
  SQL by concatenating UI filters.
- Reporting serializes dataclasses to JSON and renders Markdown by interpolating
  values. Stored ticker names, notes, claim text, URLs, and rationale are
  untrusted display data even when the database is local.
- Existing reporting separates `research` and `outcome` sections. The interface
  must preserve that semantic boundary in JSON, Markdown, and any HTML.
- Providers perform HTTP outside the reporting/CLI read path. An interactive
  history view must not instantiate a provider or silently refresh missing data.

### Trust zones

```text
User / shell arguments / browser input
              │ untrusted input
              ▼
Interface boundary: path, filters, format, bind address, output sink
              │ validated typed requests
              ▼
Read-only application services and report builders
              │ persisted, parameterized reads only
              ▼
SQLite database + raw stored text and metadata
              │ untrusted content, trusted only as evidence with lineage
              ▼
Renderer / terminal / optional browser boundary
```

If a local HTTP transport is added, it creates a separate trust boundary:
browser or local clients must be treated as potentially hostile callers. A
loopback bind is not an authorization mechanism by itself.

### Out of scope trust

The interface must not trust database text merely because the file is local,
must not trust a user-provided path merely because it exists, and must not
trust an HTTP request merely because it originates from `127.0.0.1`.

## Threat inventory

| ID | Threat | Preconditions | Impact | Risk | Required disposition |
|---|---|---|---|---|---|
| E5-T01 | Wrong or arbitrary database path | user controls `--db`/UI path | private DB read, misleading report | High | validate explicit path and permissions; show canonical path |
| E5-T02 | Path traversal / symlink escape | path chooser or import-like feature | access outside intended data area | High | no implicit path joining; resolve and confirm regular file; document symlink policy |
| E5-T03 | SQLite URI/extension abuse | URI-like path accepted | opening unintended file or special SQLite target | High | accept filesystem paths only in V1; reject URI schemes and NUL bytes |
| E5-T04 | Accidental network exposure | HTTP server binds wildcard | LAN users can read research | Critical | default loopback only; fail closed on non-loopback unless explicit opt-in |
| E5-T05 | CSRF against local HTTP | browser visits malicious page while UI server runs | state-changing/read actions driven cross-origin | High | read-only endpoints, strict Origin checks, random bearer token, no cookies |
| E5-T06 | Browser auto-open abuse | interface starts browser automatically | unexpected navigation or data exposure | Medium | no auto-open by default; explicit opt-in and safe loopback URL |
| E5-T07 | Stored XSS / HTML injection | notes, claims, rationale, URL, ticker contain markup | script execution or data exfiltration in browser | Critical | text escaping by context; no raw HTML; CSP if HTML exists |
| E5-T08 | Markdown injection | untrusted text rendered as Markdown | links/images/HTML or misleading output | High | escape or use safe Markdown subset; disable raw HTML and unsafe links |
| E5-T09 | Terminal escape injection | malicious stored text in text output | terminal manipulation or deceptive display | Medium | strip/control-escape or use a safe table renderer; test ANSI/OSC payloads |
| E5-T10 | Unsafe JSON serialization | nested dataclasses/enums or user values | malformed output, type confusion, downstream injection | High | schema-tested JSON, finite numbers, no executable deserialization |
| E5-T11 | SQL injection | UI filter, sort, ticker, or search enters query | arbitrary DB read/write | Critical | parameterize values; whitelist identifiers/order clauses; read-only connection |
| E5-T12 | Local file disclosure | source path, URL, export, or template is interpreted as file | arbitrary file content exposure | High | no file includes; restrict exports; treat URLs as strings; allowlisted output |
| E5-T13 | Secret disclosure | env/config/raw payload contains credentials | API key or credential leakage | Critical | redact secrets; never render raw payload/config; secret scanner tests |
| E5-T14 | Telemetry or provider fallback | missing record triggers network fetch | external disclosure and historical contamination | Critical | no provider imports/calls in interface; kill-switch test |
| E5-T15 | Research/outcome confusion | outcome shown beside historical thesis | hindsight presented as contemporaneous knowledge | High | typed section boundary, labels, JSON namespaces, tests |
| E5-T16 | User-note injection into reports | notes included in structured payload | stored XSS/Markdown/terminal injection | High | treat notes as untrusted text; output-context encoding |
| E5-T17 | Resource exhaustion | huge DB, long notes, pathological JSON, repeated queries | memory/CPU/disk denial of service | Medium/High | bounded pagination, field/row/output limits, query timeouts where possible |
| E5-T18 | Database mutation through UI | delete/edit/reindex endpoint or writable connection | historical evidence altered | High | read-only UI V1; SQLite read-only mode; no mutation routes |
| E5-T19 | TOCTOU/path replacement | selected DB replaced after validation | read of different file | Medium | open once and inspect file identity; avoid repeated path resolution |
| E5-T20 | Cross-origin data leak | browser page can call local endpoint | malicious site reads local history | High | token plus Origin policy; no wildcard CORS; browser mode threat review |
| E5-T21 | URL/phishing rendering | stored `source_url` is clickable | navigation to attacker-controlled site | Medium | display origin; safe `https` allowlist or non-clickable text by default |
| E5-T22 | Version/cohort omission | interface hides strategy/factor/thesis version | incompatible evidence appears identical | High | expose identity fields and reject ambiguous queries |
| E5-T23 | Error leakage | traceback includes path, SQL, secrets | local disclosure or confusing output | Medium | user-safe errors; debug output opt-in and redacted |
| E5-T24 | Lock/contention abuse | DB locked or malformed while serving | hangs or partial reports | Medium | bounded retries, read-only transaction, explicit unavailable status |

## Required controls

### Database selection and local files

- V1 accepts an ordinary filesystem path, not a SQLite URI, URL, glob, or
  arbitrary `ATTACH` target. Reject NUL bytes, control characters, URL schemes,
  and unexpected path syntax before opening.
- Display the resolved canonical path and require an explicit user choice for
  any non-default path. Do not silently fall back to another database when the
  requested file is absent or malformed.
- Define a documented default only if one is introduced. It must be inside a
  user-owned application data directory, with restrictive directory/file
  permissions where supported. Do not default to the repository root or a
  broad home-directory search.
- Resolve the path once, open it read-only, and retain the opened handle. The
  interface must not repeatedly resolve a user-controlled path during a
  request. If symlinks are allowed, state that policy and show the final target;
  otherwise reject them.
- Use SQLite read-only mode for interface sessions. Do not run migrations,
  create parent directories, write caches, or mutate rows from a read-only
  viewer. The current storage constructor is write-capable; an interface must
  use a future explicit read-only opening seam rather than assume the ordinary
  constructor is safe.
- Do not expose raw payload tables, filesystem paths, private notes, or
  credentials by default. Exports must be explicitly selected and bounded.

### Network and browser boundary

- No network is the default. A historical inspection must succeed with provider
  and HTTP kill switches active.
- If HTTP is implemented, bind to `127.0.0.1` (or `::1` when explicitly
  selected), never `0.0.0.0`, `::`, or an interface wildcard by default. Refuse
  non-loopback binds unless the user explicitly opts in and receives a warning.
- Use a per-process high-entropy bearer token for HTTP requests. Do not use
  ambient cookies or rely on loopback origin as authentication. Do not log the
  token or put it in a reusable URL.
- Default to GET/read-only routes. No state-changing methods are needed for the
  first interface. If mutations are later added, require CSRF protection,
  strict Origin/Referer validation, same-site protections, and explicit
  confirmation; never accept cross-origin `*` CORS.
- Do not auto-open a browser by default. If opted in, open only a generated
  loopback URL, avoid query-string secrets, and state that another local process
  may observe the port. Provide a visible shutdown action.
- For browser rendering use a restrictive CSP (`default-src 'self'`, no
  inline script/eval, no remote connections) and no remote fonts, images,
  analytics, or iframes. Prefer text-only/JSON and a trusted static bundle.
- Do not enable telemetry, update checks, remote error reporting, or provider
  fallback as a side effect of opening a report.

### Output encoding and serialization

- Treat all stored strings as untrusted: ticker, notes, tags, rationale,
  claims, URLs, source names, strategy metadata, and report payload values.
- JSON must be a documented schema, use finite numeric values, preserve enums
  and dates as data, and serialize no executable object hooks. Consumers must
  parse JSON, never `eval`, `pickle`, or deserialize arbitrary classes.
- Markdown output must escape or safely render user/database text. Disable raw
  HTML, dangerous URL schemes (`javascript:`, `data:`, `vbscript:`), remote
  image embedding, and untrusted link titles. A source URL should be displayed
  as text by default; clickable links need an explicit safe-URL policy.
- HTML, if added later, must contextually escape text, attributes, URLs, and
  JavaScript contexts separately. A generic HTML escape is not sufficient for
  every context. Never inject stored text into script blocks or event-handler
  attributes.
- Terminal output must not emit ANSI/OSC control sequences from stored values.
  Use a table formatter that escapes controls or replace them visibly.
- Keep research and outcome sections distinct in the domain and every output
  format. The JSON shape should have separate namespaces/section types, not a
  flat `thesis` plus `future_return` object. Markdown should include explicit
  boundary headings and no outcome fields in research payloads.
- Preserve source references, strategy/factor/thesis versions, universe/cohort,
  as-of date, and outcome horizon in displayed and machine-readable output.

### Query and database safety

- Use parameter binding for all user values. SQL identifiers, sort keys,
  directions, and selected columns cannot be parameterized safely; choose them
  from fixed allowlists only.
- Use a read-only connection and bounded transactions. Do not accept raw SQL
  from the interface. Do not expose arbitrary table/column selection.
- Add maximum page size, maximum search length, maximum serialized report size,
  and maximum note length. Reject or truncate only with an explicit status; do
  not silently alter historical data.
- Avoid loading an entire unbounded table for a browser request. Use stable,
  identity-safe pagination and deterministic ordering by date plus ID/ticker,
  never positional assumptions.
- Return generic user-facing errors for malformed requests and log only
  redacted diagnostic context. Do not return SQL, absolute paths, environment
  variables, raw payloads, or stack traces by default.

### Privacy and authored content

- Watchlist notes and tags are user-authored private data. Store and display
  them as data, with no network transmission or telemetry.
- Do not include notes in public/shareable exports unless explicitly requested.
  Consider a redaction option for reports and a visible privacy indicator.
- Treat source URLs, filing text, and claim text as untrusted external content;
  rendering them must not fetch them. No server-side URL retrieval.
- Never expose environment variables, API keys, Google credentials, raw HTTP
  headers, or provider configuration in reports or errors.

## Abuse cases and expected behavior

1. A database note contains `<img src=x onerror=alert(1)>`: it appears as
   literal text or safely escaped content; no script runs.
2. A note contains `\u001b]52;c;...`: terminal output strips or visibly escapes
   the control sequence.
3. A user supplies `file:///etc/passwd`, `../../secret.db`, a NUL byte, or a
   SQLite URI: the interface rejects it as an invalid database path.
4. A missing historical metric exists in a provider today: the interface
   reports missing/insufficient data and makes no provider call.
5. A malicious web page requests `http://127.0.0.1:<port>/research`: the
   request is denied without the per-session token and/or fails Origin policy.
6. A stored outcome is +500%: it appears only under post-hoc outcome sections;
   the historical thesis, classification, drivers, and watch state are byte-
   or structure-equivalent to their pre-outcome values.
7. Two databases contain the same ticker: the selected canonical path and
   database identity remain visible; no silent merge occurs.
8. A huge note or result set is requested: the request is bounded and returns a
   clear limit/pagination response rather than allocating unbounded memory.

## Test matrix

| Area | Test | Expected result |
|---|---|---|
| Path | relative traversal, absolute outside root, NUL, URI scheme, symlink policy | reject or follow only documented policy; no unintended file read |
| Path | missing DB, directory, non-SQLite file, wrong schema | explicit error; no fallback database |
| Path | replace selected path after validation | opened file identity remains the selected one or request fails |
| SQLite | quote-heavy ticker/search/note | no SQL injection; exact parameterized behavior |
| SQLite | sort/filter values and identifiers | allowlist only; injection strings rejected |
| SQLite | read-only connection attempts write/migration | denied; existing data unchanged |
| Serialization | NaN, infinity, dates, enums, nested dataclasses | schema-valid finite JSON; no executable deserialization |
| Markdown | HTML tags, links, raw HTML, `javascript:`/`data:` URLs | escaped/non-clickable/blocked according to policy |
| HTML | script, attribute, URL, CSS-context payloads | no execution or unsafe navigation; CSP enforced |
| Terminal | ANSI/OSC/control characters | rendered harmlessly, no terminal state change |
| Privacy | notes/tags/raw payload/config with secret-like values | rendered only when requested; secrets redacted/not transmitted |
| Network | provider and HTTP kill switches during all history reads | commands succeed from persisted data without network calls |
| HTTP | default bind inspection | loopback only; wildcard bind rejected by default |
| HTTP | missing/invalid token, hostile Origin, cross-site form/fetch | denied; no CORS wildcard; no CSRF path |
| Browser | auto-open disabled; opt-in URL has no secret in query | no browser launch by default; safe loopback launch when opted in |
| Resources | huge result set/note/JSON nesting/repeated requests | bounded response, pagination/limit, deterministic failure |
| Time boundary | T0 report plus later filing/price/outcome | research sections unchanged; outcome separately labeled |
| Identity | strategy/factor/thesis version, universe, benchmark, horizon changes | displayed and not silently mixed |
| Report | text, JSON, Markdown from same persisted report | same source lineage and research/outcome separation |
| Persistence | close/reopen and provider-kill inspection | identical historical interpretation; no recomputation |
| User content | watch note round-trip containing markup and secrets-like text | preserved as data, safely rendered, not transmitted |

## Security review gates

The interface is not ready for implementation approval until all of the
following are explicit in its contract and tests:

- database path policy and read-only opening behavior;
- network default and bind-address rejection behavior;
- browser auto-open policy;
- output-context encoding for terminal, Markdown, JSON, and any HTML;
- no-provider/no-telemetry guarantee;
- research-versus-outcome structure in every output format;
- bounded query and serialization behavior;
- user-authored note privacy and rendering policy;
- secret redaction and error policy;
- provider-kill, information-barrier, and version/cohort identity tests.

## Non-goals for E5

- No live trading, broker integration, or write-capable portfolio actions.
- No public web deployment, LAN sharing, reverse proxy, cloud hosting, or
  authentication system for remote users.
- No background daemon, websocket, polling, notifications, or provider refresh.
- No raw SQL console, arbitrary file browser, upload/import endpoint, or URL
  fetcher.
- No frontend financial calculations or duplicated strategy logic.
- No LLM, analytics telemetry, ad/usage tracking, remote logging, or crash
  upload.
- No claims that local-only HTTP is a complete security boundary for a
  multi-user machine.

## Recommended safe baseline

The lowest-risk first implementation is a read-only CLI/report surface over an
explicit SQLite path, with JSON and safely escaped Markdown output. If an
interactive browser is later justified, use a local-only, token-protected,
read-only loopback server with no auto-open, no external resources, strict
content security policy, bounded endpoints, and provider/HTTP kill-switch
tests. Any non-loopback mode should be a separately reviewed deployment mode,
not a hidden configuration toggle.

## Required workstream report

**WORKSTREAM:** E5-S — Interactive Research Interface security/privacy review
**STATUS:** COMPLETED — threat model delivered; implementation not authorized
**Scope completed:** assets, trust boundaries, path/database threats, network
exposure, XSS/HTML/Markdown, JSON, SQL injection, local file disclosure, CSRF,
browser auto-open, secrets, telemetry, provider fallback, historical/outcome
confusion, resource exhaustion, authored notes, safe bind defaults
**Files created:** `docs/security/interactive-research-interface.md`
**Files modified:** none
**Contracts consumed:** existing CLI/reporting/storage/domain behavior and Wave E
architecture documentation
**Tests added:** none; this fenced security workstream is documentation-only
**Tests executed:** read-only source inspection; no repository mutation
**Results:** threat inventory, required controls, abuse cases, release gates,
test matrix, and non-goals documented
**Assumptions:** first interface is local/read-mostly; HTTP is optional and not
currently assumed; existing historical artifacts are the source of truth
**Known limitations:** no runtime HTTP implementation was available to test;
path permissions and platform-specific browser behavior require validation when
an implementation exists
**Dependencies:** E5 interface contracts, read-only SQLite opening seam,
renderer implementation, and CLI integration tests
**Recommended next action:** freeze the safe baseline and require the listed
security tests before any browser/HTTP implementation is accepted.
