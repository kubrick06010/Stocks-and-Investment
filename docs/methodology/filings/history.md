# Filing section history comparison

`FilingHistoryComparator` compares two already-persisted `FilingDocument`
snapshots and their parsed `FilingSection` records. It is deterministic and
evidence-first: it does not fetch data, inspect current providers, infer
business meaning, or make causal claims.

## Identity and point-in-time rules

Sections are aligned by the normalized pair `(item, kind)`, using collapsed
whitespace and case-folding. Ordinal position is never used. Duplicate keys,
sections belonging to another filing, different tickers, same filing IDs, and
future-to-past availability order are rejected. A later amendment is a distinct
filing and can be compared when its availability is not earlier than its
predecessor.

Parser versions must match by default. Callers may explicitly opt into
`allow_parser_mismatch=True`; that is an acknowledged limitation, not an
automatic compatibility claim.

## Similarity and methodology

`filing_section_diff_v1` tokenizes normalized text with Unicode word tokens and
uses `difflib.SequenceMatcher` with `autojunk=False`. The policy defaults are:

- similarity >= 0.98: `SECTION_UNCHANGED`;
- similarity < 0.98: `SECTION_MODIFIED`;
- similarity < 0.90: `material=True`.

Added and removed sections are material by definition. Thresholds and their
methodology version are configurable and are included in every change record.
The result is a text-difference classification only; it does not establish
that a disclosure is economically important, true, risky, or causal.

## Evidence lineage and determinism

Each change carries source references to the original section spans and content
hashes. IDs are SHA-256-derived from filing IDs, section IDs, change type, and
methodology version. Results are sorted by normalized section identity, so
reordered inputs produce the same output.

Whitespace/punctuation noise can be classified unchanged because similarity is
token-based. Parser differences should normally be resolved upstream by using
the same parser version; explicit opt-in exists for controlled unsupported
comparisons and must remain visible in the caller's audit trail.

This module does not persist or mutate historical documents. Later filings,
amendments, outcomes, or parser versions cannot rewrite an already-created
`FilingSectionChange` object.
