# Wave E2 data flow

```text
SEC/archive metadata + bytes
        -> content hash and FilingDocument
        -> bounded safe HTML normalization
        -> versioned FilingSections with source offsets
        -> evidence references
        -> deterministic/analyst-authored QualitativeClaims
        -> FilingEvidenceSnapshot

Persisted filing T0 + persisted filing T1
        -> identity-aligned section diff
        -> FilingSectionChanges
        -> later thesis/report integration
```

Provider code performs HTTP. Parsing, change detection and claim construction
are pure. Historical consumers read persisted snapshots and never fetch or
reparse old filings implicitly.
