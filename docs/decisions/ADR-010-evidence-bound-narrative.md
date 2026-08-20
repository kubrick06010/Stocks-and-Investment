# ADR-010: Evidence-bound optional narrative layer

## Decision

Keep narrative generation downstream of `ResearchReport`. Ship a deterministic
structured renderer and an explicitly disabled optional LLM renderer. Do not
add an LLM SDK, provider credentials, network access or persistence in E6 V1.

## Rationale

This preserves the distinction between validated research evidence and prose.
It also keeps historical rendering reproducible and allows a later renderer to
be added without changing calculations, classifications, outcomes or source
lineage.

## Consequences

The current renderer is intentionally not a conversational or creative model.
Future model-backed renderers require a separate security and reproducibility
review, must consume structured evidence, and must preserve the explicit
research/outcome boundary.
