# Wave E3 dependency and ownership map

```text
domain/automation + interfaces/automation (frozen)
        |
        +-- E3A trigger detection (schedule/filing/manual adapters)
        +-- E3B deterministic pipeline orchestration
        +-- E3C SQLite automation persistence
        +-- E3D retry/idempotency/failure control
        +-- E3E reporting/CLI inspection
        +-- E3F adversarial integration and provider kill switch
```

E3B may call only public services from filing ingestion, screening, thesis,
history, watchlist and reporting. E3 agents may not place analytical formulas
inside automation. Shared domain, interfaces and SQLite migration remain under
Program Lead ownership.
