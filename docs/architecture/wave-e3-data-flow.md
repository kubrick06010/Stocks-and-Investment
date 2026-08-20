# Wave E3 data flow

```text
manual/schedule/persisted filing availability
                  |
                  v
       immutable AutomationTrigger
                  |
                  v
   idempotent ResearchAutomationOrchestrator
                  |
        +---------+----------+---------+---------+
        v                    v         v         v
 existing evidence      ResearchRun  thesis   changes/watchlist/report
 ingestion/PIT views      services   service      existing services
        |                    |         |              |
        +--------------------+---------+--------------+
                             v
                artifact SourceReferences
                             |
                             v
                    durable AutomationRun
```

Every analytical artifact is created by its existing owner. Automation records
lineage and failure state; it does not calculate metrics, scores, theses or
watch conditions itself.
