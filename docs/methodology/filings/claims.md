# Deterministic filing claims (Wave E2 V1)

The claims layer is evidence-first and intentionally narrow. It consumes
persisted `FilingDocument` and `FilingSection` records; it never downloads a
filing, calls a provider, interprets arbitrary prose with an LLM, or falls
back to current data.

## Two supported claim methods

`build_analyst_authored_claim` creates a `SUPPORTED` claim only when the
caller supplies at least one `FilingEvidenceReference`. Every reference must:

- identify the same filing and an existing section;
- be bounded by that section's source span and normalized text;
- have an excerpt hash equal to SHA-256 of the selected normalized text;
- be usable at the claim's `as_of` date, meaning the filing was publicly
  available by then.

The factory accepts local normalized-text coordinates for compact fixtures and
absolute section coordinates for persisted anchors. Generated IDs hash the
complete claim identity, methodology, statement and evidence references, so
rerunning the same input is stable. `created_at` is provenance metadata and is
not part of the identity.

`build_disclosed_risk_claims` is deterministic presence detection. A caller
must predeclare each literal pattern and the allowed `FilingSectionKind`.
The implementation emits at most one claim per pattern and section, citing the
first deterministic match. Its statement means only that the configured text
was disclosed in that section. It does not infer probability, severity,
causality, management intent, resolution, fraud, or investment impact.

## Hash and span semantics

`normalized_excerpt_hash(text)` returns `sha256:<hex digest>` over UTF-8
encoded normalized excerpt text. Both this canonical form and a bare SHA-256
hex digest are accepted when validating an existing reference. A hash mismatch
or cross-filing/cross-section span raises `ValueError`; no unsupported claim is
silently downgraded to a neutral result.

Generated deterministic references use the section's absolute
`source_start + normalized-match-offset` coordinates. Analyst fixtures may use
local coordinates when their source coordinate system is not available. The
resolved excerpt is always sliced from the exact immutable `normalized_text`
of the referenced section.

## Point-in-time and immutability

The filing's `available_at` date is checked against `as_of`. A later filing
cannot contribute to an earlier claim. Previously constructed immutable
`QualitativeClaim` values are not updated when another filing is added; a new
filing produces a new claim identity and historical record.

## Explicit limitations

This V1 does not determine whether a disclosed risk is material, likely,
resolved, truthful, or economically causal. Pattern presence is evidence of a
disclosure, not an assessment of the issuer or an investment recommendation.
Analyst-authored statements remain human interpretation and must stay linked
to their cited evidence. Raw HTML/active content is outside this layer; input
normalization and safe inert parsing belong to the ingestion boundary.
