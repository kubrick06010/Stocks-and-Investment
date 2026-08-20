# Wave D contracts

Wave D is an evidence interpretation layer over immutable Wave B/C records.
Its domain contracts are in `domain/research_intelligence.py` and its service
seams are in `interfaces/research_intelligence.py`.

The primary invariants are:

- `ThesisSnapshot` references exactly one historical ResearchRun and Result.
- `ResearchChangeEvent` compares persisted artifacts from two runs.
- `FactorOutcomeObservation` keeps factor `as_of` separate from its future
  outcome horizon. Universe, benchmark, base currency, and rebalance cadence
  are part of the cohort identity and must match the requested cohort.
- Strategy comparisons expose assumption mismatches instead of hiding them.
- Reports and watchlist entries retain source references.
- All methodologies have explicit version fields where interpretation can
  change.

These contracts were frozen in D0 and are now implemented. Cohort identity was
strengthened additively during the Wave D closure gate after a concrete mixing
risk was demonstrated.
