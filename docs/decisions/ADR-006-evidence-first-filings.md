# ADR-006: Evidence-first qualitative filings

Status: Accepted for Wave E2 contract freeze.

## Decision

Store immutable filing identity/content hashes and deterministically parsed
sections before creating qualitative claims. Claims require exact source
references and a methodology version. Deterministic and analyst-authored claims
remain distinguishable. Later amendments and parser/methodology versions create
new artifacts; they do not overwrite history.

## Consequences

- historical qualitative research remains PIT and auditable;
- raw provider payloads and prose interpretations cannot leak into financial
  calculations implicitly;
- V1 can provide section/change intelligence without an LLM;
- business-specific inference remains deliberately limited until stronger
  evidence and validation exist.
