# Deterministic automation orchestrator

`DeterministicAutomationOrchestrator` is the E3 control-plane implementation.
It coordinates existing research services; it does not calculate metrics,
fetch providers, query storage, or create a second research engine.

## Contract

The orchestrator requires one injected `StepAdapter` for each frozen pipeline
step, in this exact order:

1. `ingest_evidence`
2. `normalize_observations`
3. `create_research_run`
4. `generate_thesis`
5. `detect_changes`
6. `evaluate_watchlist`
7. `build_report`

Each adapter receives the immutable definition, trigger and all source
references known so far. It returns only the references to artifacts it
produced. Those references become the inputs to the next step and are retained
in the `AutomationRun` and its step records.

## Identity and idempotency

The run ID is a SHA-256 identity derived from definition ID/version, pipeline
version, trigger kind, trigger deduplication key and research `as_of` date.
The idempotency key is the definition version plus the trigger's stable
deduplication key. An injected reader can return an existing durable run before
any step is called. No current data or provider fallback is attempted.

## Failure semantics

Typed `AutomationStepFailure` values may be retried immediately when their
failure kind is allowed by the definition's `RetryPolicy`. There are no sleeps
or hidden retries. Unknown exceptions become permanent failures with their
type and message recorded. A failure stops the ordered pipeline; unexecuted
steps are explicitly `SKIPPED`.

* all steps completed → `COMPLETED`;
* a failure after at least one completed step → `PARTIAL_FAILURE`;
* failure before any step completes, or invalid/disabled input → `FAILED`.

The failed step retains its typed failure kind, attempt and message. A failed
run is never represented as completed.

## Scope and limitations

The current implementation is an injected, synchronous runner intended for
manual/CI execution and deterministic tests. It does not schedule jobs, sleep
between retries, persist runs itself, coordinate concurrent workers, or infer
point-in-time availability. Existing services and persistence adapters retain
those responsibilities. A later integration layer may provide the `read` and
`write` callbacks without changing the orchestration semantics.
