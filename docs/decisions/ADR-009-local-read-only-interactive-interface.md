# ADR-009: Local read-only interactive interface before HTTP

Status: accepted for Wave E5 V1

## Context

The roadmap calls for an interactive research interface over immutable
historical artifacts. A browser UI offers strong navigation, but creates a new
network, origin, injection, authentication and dependency boundary. The current
package has no runtime dependencies and already exposes typed reports and a
provider-free CLI.

## Decision

E5 V1 adds a typed read-only query service and a standard-library terminal
session. It opens an explicitly selected SQLite database in read-only mode,
uses existing reports/services, and supports deterministic text, JSON and
Markdown output. It creates no listening socket, does not auto-open a browser,
does not persist session state and adds no runtime dependency.

HTTP, server-rendered HTML, a TUI framework and a SPA remain separate future
decisions. An HTTP implementation requires its own security contract covering
loopback binding, authentication/token policy, origins, CSRF, CSP, output
escaping, resource limits and privacy.

## Consequences

- Historical inspection remains offline and cannot migrate or mutate the DB.
- `ResearchReport` remains the canonical presentation-neutral payload.
- Outcome visibility is an explicit request policy and outcomes remain in
  separate sections.
- The first interface favors correctness and portability over visual density.
- Browser UX is deferred, not prohibited; it must consume the same query seam.
