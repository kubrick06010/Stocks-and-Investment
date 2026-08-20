# Wave E5 dependency and ownership map

```text
domain/interactive + interfaces/interactive (frozen)
        |
        +-- E5A read-only SQLite opening seam
        +-- E5B provider-free query service
        +-- E5C local terminal session
        +-- E5D safe text/Markdown/JSON rendering
        +-- E5E CLI integration
        +-- E5F adversarial path/injection/information-barrier review
```

E5 consumes storage, comparison, factor research, reporting and other public
read services. It may not modify their analytical implementations. Shared
domain/interfaces, SQLite constructor/export and CLI integration remain under
Program Lead ownership. Feature agents receive disjoint exact-file fences.

No E5 implementation owns providers, scoring, strategies, backtesting,
portfolio accounting or research automation.
