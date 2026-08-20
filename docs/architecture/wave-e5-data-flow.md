# Wave E5 data flow

```text
explicit local database path
          |
          v
SQLite read-only adapter (no migration/write)
          |
          v
ResearchViewRequest --typed identities/as-of/version/horizon--+
          |                                               |
          v                                               |
provider-free InteractiveResearchService                  |
          |                                               |
          +--> persisted thesis/change/watch/filing data  |
          +--> persisted backtest comparison              |
          +--> persisted factor outcomes                  |
          +--> persisted automation/construction results  |
          |                                               |
          v                                               |
ResearchReport / ResearchView <----------------------------+
          |
          +--> safe terminal text
          +--> deterministic JSON
          +--> safe Markdown
```

Research sections contain only historical evidence available to their source
runs. Persisted future outcomes may be queried post hoc but remain separate in
the report model and every renderer.
