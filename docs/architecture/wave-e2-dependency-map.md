# Wave E2 dependency and ownership map

```text
domain/filings + interfaces/filings (frozen)
        |
        +-- E2A provider metadata/content adapter
        +-- E2B safe parser/section normalizer
        +-- E2C deterministic claims/evidence
        +-- E2D section history/change detection
        +-- E2E SQLite v8 persistence
        +-- E2F reports/CLI integration
```

Feature modules consume domain contracts. They may not modify shared domain,
interfaces or storage. Storage integration is a Program Lead-owned additive
migration. Reporting consumes persisted E2 artifacts and must not parse filings.
