# Wave E3 independent adversarial review

Status: **VALIDATED within the documented synchronous V1 scope**

Reviewer scope was fenced to:

- `tests/integration/test_wave_e3_adversarial.py`
- this document

No production code, contracts, storage implementation, existing tests, status
files, or roadmap files were modified.

## Attacks executed

The adversarial suite covers:

- filing records physically present in SQLite but invisible before
  `available_at`;
- stable per-filing trigger identity when a later filing is added;
- manual replay and deterministic trigger identity;
- definition and pipeline version identity;
- existing terminal/in-flight run behavior;
- retry budget and forbidden retry kinds;
- partial failure and downstream skipping;
- immutable SQLite conflicts and close/reopen;
- additive v8 → v9 migration with an existing raw payload;
- UTC schedule boundaries and exact cron-minute matching;
- provider-free filing inspection after database reopen;
- an explicit research/outcome information-boundary attack.

## Findings

### E3-F1 — strategy version was absent from automation run identity

**Severity: release-blocking integrity defect — fixed.**

The independent regression showed that `strategy_v1` and `strategy_v2` could
share an execution identity. The canonical key now hashes definition identity,
pipeline version, strategy name/version, universe, canonical parameters and
trigger key. The orchestrator uses that one helper, so strategy and parameter
changes create distinct runs.

The failing regression is
`test_manual_trigger_replay_and_definition_pipeline_strategy_versions_are_distinct`.

Expected independently: changing a strategy methodology must create a distinct
execution identity, just as changing the pipeline or definition version does.

The original red test now passes. The existing-terminal replay fixture was also
updated to construct its expected key through the canonical identity helper;
this preserves the independent economic expectation rather than hard-coding
the obsolete key format.

## Outcome information barrier

The adversarial test confirms that `AutomationTrigger` rejects
`outcome_observation`, `research_outcome`, and
`factor_outcome_observation` references before orchestration. This is the
expected boundary: later outcomes cannot become research inputs.

## Results

The focused review suite reports **11 passed** after the lead fix.

Existing E3 tests already provide additional coverage for SEC/provider
behavior, retry decisions, migration, and persistence. Full quality-gate
results must be recorded after the lead decides whether this defect is to
remain as a release blocker or be fixed in a separately authorized change.

## Limitations

- SQLite itself serializes the tested duplicate identity conflict, but the
  review does not claim distributed locking or a cross-process atomic claim
  protocol for concurrent workers.
- The trigger source is provider-free by construction; this suite verifies
  reopened persisted filing access, not live network behavior.
- Cron validation covers the documented five-field UTC subset. It does not
  claim full Vixie-cron DOM/DOW semantics.
- No outcome value is used to make a research decision in the adversarial
  tests; the trigger-level rejection test confirms the current boundary.
