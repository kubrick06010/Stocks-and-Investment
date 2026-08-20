# Interactive research rendering

`render_research_view` is a deterministic, provider-free edge adapter for a
frozen `ResearchView`. It does not recalculate research or fetch current data.

## Formats and safety

The supported formats are `text`, `json`, and `markdown`. JSON uses sorted
keys, explicit dataclass/enum/date conversion, finite numeric values only, and
stable compact separators. Stored strings are treated as untrusted: terminal
control sequences, ANSI/OSC payloads, raw HTML, and Markdown link/image
delimiters are neutralized before rendering.

The renderer accepts an optional character limit and raises an explicit error
when the result exceeds it. It never truncates silently.

## Historical boundary

Report sections retain their original `section_type`, payload, source
references, and versions. The rendered representation additionally exposes
`research_sections` and `outcome_sections` and labels them separately in text
and Markdown. A subsequent outcome is never flattened into the historical
research section.

## Determinism

Identical frozen inputs produce identical output. Reports remain presentation
of persisted evidence; provider access, recomputation, and current-data
fallbacks are outside this module.
