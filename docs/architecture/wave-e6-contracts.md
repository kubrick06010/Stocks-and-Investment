# Wave E6 contracts: evidence-bound narrative

E6 is an optional downstream layer. `NarrativeRequest` consumes a persisted
`ResearchReport`; it never consumes raw provider payloads or performs metrics.
`NarrativeResult` records renderer and policy versions, status, source references
and an explicit information boundary (`research_only` or
`research_then_outcome`).

The default renderer is deterministic and structured. The optional LLM slot is
represented by an explicit disabled renderer in V1, so no model, secret,
network call or generated prose is required for core research functionality.
