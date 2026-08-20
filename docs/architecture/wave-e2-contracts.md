# Wave E2 evidence-first filing contracts

Wave E2 separates four immutable layers:

1. `FilingDocument`: SEC/archive identity, acceptance/public availability,
   retrieval time and content hash;
2. `FilingSection`: deterministic normalized text plus source offsets and parser
   version;
3. `FilingEvidenceReference`: exact filing/section/span/hash lineage;
4. `QualitativeClaim`: versioned interpretation supported by those references.

`FilingSectionChange` compares two persisted section snapshots. It never
regenerates the older document from a newer filing. `FilingEvidenceSnapshot`
freezes the filing, section and claim IDs available to downstream research.

The V1 classification vocabulary is intentionally small. A supported claim
requires evidence; deterministic extraction and analyst-authored claims are
distinguished. No LLM is required or authoritative.

## Information barrier

A filing is research-visible only on or after `available_at`. `period_end`,
`filed_at`, `available_at` and `retrieved_at` remain distinct. Later amendments
are new documents and may not rewrite the original snapshot.
