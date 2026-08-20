# Interactive terminal session

The terminal session is a small, read-only adapter over the frozen
`InteractiveResearchService` protocol. It injects two dependencies:

- a service implementing `query(ResearchViewRequest) -> ResearchView`;
- a renderer converting the returned view to text.

The shell never opens SQLite, calls a provider, calculates metrics, mutates
research state, or executes shell commands. Every command is parsed with
`shlex`; shell metacharacters, malformed options, and unknown commands are
rejected before the service is called.

## Commands

```text
stock TICKER [--as-of YYYY-MM-DD] [--outcomes]
thesis-history TICKER [--as-of YYYY-MM-DD]
changes TICKER [--as-of YYYY-MM-DD]
watchlist
filing FILING_ID [--as-of YYYY-MM-DD]
filing-history TICKER [--as-of YYYY-MM-DD]
backtest BACKTEST_ID [--as-of YYYY-MM-DD] [--outcomes]
compare BACKTEST_ID_A BACKTEST_ID_B [--as-of YYYY-MM-DD] [--outcomes]
factor FACTOR --factor-version VERSION --horizon HORIZON [--as-of YYYY-MM-DD] [--outcomes]
automation RUN_ID [--as-of YYYY-MM-DD]
construction CONSTRUCTION_ID [--as-of YYYY-MM-DD]
help
quit | exit
```

`--outcomes` maps to `OutcomeVisibility.SEPARATE`; it does not merge future
outcomes into historical research sections. Factor version and horizon are
mandatory for factor efficacy queries. Request IDs are SHA-256 identities of
the canonical command fields, so repeating a command in a session produces
the same request identity and does not imply a mutation.

The session is intentionally local and synchronous. It is a presentation
edge; persistence, point-in-time filtering, provenance and report semantics
remain responsibilities of the injected service.
