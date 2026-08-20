# Filing reporting methodology

`stocks_investment.reporting.filings` assembles reports from persisted
`FilingDocument`, `FilingSection`, `QualitativeClaim`,
`FilingSectionChange`, and `FilingEvidenceSnapshot` records. It does not call a
provider, parse HTML, calculate a thesis, or regenerate historical data.

## Evidence boundary

Filing evidence is reported with its filing ID, source URL, document hash,
period end, filed/available/retrieved timestamps, section content hash, parser
version, and bounded source offsets. Normalized section text is HTML-escaped
for safe Markdown/text rendering; the content hash remains the identity of the
persisted evidence. Active HTML is never emitted by the report payload.

## Interpretation boundary

Qualitative claims are a separate `interpretation` section. Each claim retains
its status, category, direction, deterministic/analyst-authored method,
methodology version, and filing evidence references. Empty claims and
`insufficient_evidence` claims remain explicit; neither is converted into a
positive or negative investment conclusion.

## Filing history

History reports contain the current evidence, deterministic claims, and a
separate `history` section for persisted section changes. A later filing is not
represented as knowledge available at the earlier filing date. The report
metadata explicitly records this boundary. Changes are keyed by filing and
section identity and retain the comparison methodology version, similarity,
materiality, rationale, and evidence references.

## Rendering

The module delegates JSON and Markdown rendering to the generic reporting
adapters. The canonical report remains structured `ResearchReport` data with
typed section kinds (`evidence`, `interpretation`, and `history`), so future
adapters do not need to reconstruct provenance from prose. No outcome or thesis
section is invented by the filing report; those belong to later research layers
and must be visibly separated when composed into a larger report.
