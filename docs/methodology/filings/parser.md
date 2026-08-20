# Safe filing parser v1

`SafeFilingParser` is a bounded, dependency-free normalization boundary for
canonical `FilingDocument` bytes. It accepts UTF-8 `text/html`,
`application/xhtml+xml`, and `text/plain` only. MIME parameters are ignored
after the media type is validated; all other types fail closed.

HTML is treated as inert input. Scripts, styles, SVG, frames, objects, forms,
templates, comments, tags, links, attributes, and external resources are not
executed, resolved, or preserved as markup. Text is entity-decoded, C0/DEL
controls are made harmless, and whitespace is normalized only in returned
section text. No network API exists in this module.

## Limits and diagnostics

The defaults are 5 MB received bytes, 5 million normalized characters, and 100
sections. Limits are constructor-injected through `ParseLimits` and violations
raise `ValueError` before a partial trusted result is returned. The parser
does not attempt archive or XML expansion; unsupported media types are rejected.

Repeated recognized headings are all returned in source order. This is
deliberate: a table of contents and the actual section can share a heading, and
the parser cannot safely infer the correct occurrence from text alone. In that
case `diagnostics` contains an explicit ambiguity message and each affected
section has `metadata["duplicate_heading"] = True`. Downstream policy must
choose or review the occurrence; the parser never silently drops one.

## Sections and provenance

The initial map recognizes Business (`Item 1`), Risk Factors (`Item 1A`),
MD&A (`Item 7`), Market Risk (`Item 7A`), Financial Statements (`Item 8`),
and Controls (`Item 9A`), including common punctuation, apostrophe, and title
variants. Sections retain their observed item/title, ordinal, SHA-256 of
normalized UTF-8 text, parser version, and UTF-8 byte offsets into the exact
input bytes. The raw filing hash and availability/PIT metadata remain owned by
`FilingDocument`; this parser does not rewrite them.

Malformed HTML is handled as text/tag input and produces deterministic output.
Malformed UTF-8, oversized input, unsupported MIME, and excessive section count
are explicit failures. Hashes are integrity identifiers, not authenticity
proof. Text extraction can lose layout, tables, footnotes, and semantic meaning;
absence of a section or phrase is not evidence that the underlying risk is
absent.

The parser returns the frozen `tuple[FilingSection, ...]` contract. Diagnostics
are exposed on the parser instance for the immediately preceding call and are
not persisted as a second contract. Callers should persist parser version,
source filing identity, section hashes, and any review decision about duplicate
headings alongside the canonical section records.
