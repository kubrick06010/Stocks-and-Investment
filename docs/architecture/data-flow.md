# V2 data flow

```text
provider -> raw cache -> normalized observation
         -> provenance/PIT validation -> snapshot
         -> pure metrics -> factor scores -> screen result
         -> research run + thesis snapshot -> CLI/report

historical run date
  -> select observations where available_at <= run date
  -> apply versioned universe/strategy
  -> construct transactions
  -> portfolio ledger + benchmark
  -> performance and validation report
```

Providers never calculate business metrics, and CLI/reporting never performs financial arithmetic.
