# Wave D data flow

```text
ResearchRun / ResearchResult / FactorScore / CriterionResult
                         │
                         ├── ThesisSnapshot
                         │       └── ResearchChangeEvent (T0 → T1)
                         ├── StrategyComparison
                         ├── FactorOutcomeObservation
                         │       └── FactorEfficacySummary
                         ├── WatchlistEntry
                         │       └── MonitoringEvent (new ResearchRun only)
                         └── ResearchReport / ReportSection
```

Historical decisions are read-only inputs. Future outcomes are permitted only
in post-hoc efficacy and outcome views. A renderer may transform a structured
report into JSON, Markdown, HTML or CLI tables, but those formats are not
canonical domain state.
