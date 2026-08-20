# Wave E6 data flow

```text
SQLite persisted evidence
        ↓ read-only service
ResearchReport (structured sections + source references)
        ↓ NarrativeRequest + versioned NarrativePolicy
StructuredNarrativeRenderer
        ↓
NarrativeResult (text/status/boundary/lineage)
        ↓
CLI text, JSON or Markdown
```

Outcome sections are excluded by default. When explicitly requested, they are
rendered only after a visible `SUBSEQUENT OUTCOME` boundary.
