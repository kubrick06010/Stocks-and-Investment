# Wave E2G — adversarial security and integrity review

## Scope

This review is independent and edits no production code. It exercises the E2A–D
filing components through:

- SEC availability semantics: acceptance/public availability, filed date and
  period end;
- inert parsing of hostile HTML/text, entities, controls, duplicate/TOC
  headings, MIME and resource limits;
- evidence span and excerpt-hash validation, cross-filing isolation and
  deterministic claim generation;
- filing-history identity alignment under reordering, additions and removals;
- immutable SQLite insert-once behavior and close/reopen read-back;
- SEC content hash validation and unsafe document-path rejection.

Expected values were derived from the fixture inputs, not from production
helpers. No network was used.

## Initial result

Focused command:

```text
python3 -m pytest -q -p no:cacheprovider tests/integration/test_wave_e2_adversarial.py
1 failed, 13 passed
```

The initial failing test was release-blocking:

`test_parser_rejects_unclosed_active_markup_instead_of_exposing_script_text`

Input contains an unclosed `<script>` element whose body includes:

```text
Item 1A Risk Factors
password=secret
<h1>Item 1A Risk Factors</h1><p>Visible evidence</p>
```

Expected behavior: all active-markup content is discarded or the document is
rejected fail-closed; hostile text must not become a filing section or evidence.

Observed behavior: `SafeFilingParser.parse()` returns a section whose
`normalized_text` contains `password=secret`. The parser's paired-tag regular
expression removes closed active blocks, but an unclosed active block reaches
the generic tag stripper and is treated as visible filing text. Production was
not modified, per the adversarial-review fence.

The other 13 focused attacks passed, covering:

- closed script/style/iframe inertness, entity decoding and control removal;
- unsupported MIME and byte/text limits;
- duplicate headings retained with diagnostics rather than silently collapsed;
- cross-filing references and altered excerpt hashes/spans rejected;
- deterministic claims and future filing invisibility;
- acceptance timestamp controlling visibility rather than period end or filing
  date alone;
- oversized and unsafe SEC primary documents rejected;
- SEC content-hash tampering rejected;
- identity-safe filing history under reorder/asymmetric section sets;
- immutable SQLite conflict detection and close/reopen preservation.

## Resolution

The parser now masks complete active-markup blocks without changing source
coordinates and fails closed for an unmatched active opening tag by masking the
remainder of the document. The regression covers the active tag families used
by the parser and confirms that hostile script text cannot become a filing
section, evidence excerpt or qualitative claim.

Final focused adversarial result:

```text
14 passed
```

Final project quality gate:

```text
304 passed, 1 intentionally skipped live-provider test
ruff: PASS
mypy: PASS
compileall: PASS
git diff --check: PASS
```

## Security and integrity assessment

The observed content-boundary defect was confirmed and fixed. Malformed active
markup is now excluded from section detection, evidence hashes and qualitative
analysis. The independent attack suite is green and E2 can be validated within
its documented V1 limits.

No evidence was found in this review of:

- provider calls from claim/history functions;
- future filing visibility through the tested acceptance boundary;
- cross-filing evidence reference acceptance;
- silent mutation of persisted filing documents, sections or claims;
- positional section alignment in the tested history comparator.

## Remaining limitations

- The parser is intentionally lexical and dependency-free; it does not preserve
  complex table/layout semantics.
- Duplicate section headings remain explicit and ambiguous comparisons are
  rejected instead of guessed.
- The SEC adapter currently covers recent submissions metadata rather than the
  complete historical submissions archive.
- Qualitative claims are deterministic disclosed-pattern or analyst-authored
  claims; no semantic business inference or LLM interpretation is asserted.
