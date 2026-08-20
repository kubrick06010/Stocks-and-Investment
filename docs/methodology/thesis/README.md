# Structured thesis V1

`StructuredThesisEngine` maps persisted factor scores and criterion results to
versioned, source-referenced thesis snapshots. It has no provider access and
does not produce execution advice. Classification rules are deterministic:
missing evidence yields `INSUFFICIENT_DATA`, scores at least 80 yield
`ATTRACTIVE` unless a criterion failed (then `WATCH`), scores 60–79 yield
`WATCH`, and lower scores yield `NEUTRAL`.
