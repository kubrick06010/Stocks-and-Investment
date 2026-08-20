# E3D reliability and idempotency helpers

E3D contains pure decisions used by the future automation runner. It does not
persist runs, execute pipeline steps, sleep, schedule jobs, or add random
jitter. Keeping these decisions pure makes retry plans and replay behavior
testable and reproducible.

## Idempotency

The canonical key is:

`definition.version + ":" + trigger_key`

The definition version is part of the key so a changed automation definition
cannot silently replay an execution created under an older methodology. The
trigger key is required and is not whitespace-normalized; upstream trigger
identity must remain visible in diagnostics.

## Run states

The direct transitions are:

- `CREATED → RUNNING`
- `CREATED → CANCELLED`
- `RUNNING → COMPLETED | PARTIAL_FAILURE | FAILED | CANCELLED`

Terminal states cannot transition again. `CREATED` is resumable/claimable,
`RUNNING` is in flight, and terminal runs are immutable replay results.

## Retry policy

Retry eligibility requires both conditions:

1. the typed failure is listed in `RetryPolicy.retryable_failures`; and
2. the failed attempt is below `max_attempts`.

Therefore invalid input, integrity violations, and permanent failures do not
retry under the default policy. A caller may explicitly opt one of them into a
policy, which is visible and testable rather than implicit.

For failed attempt `n`, the delay is:

`min(initial_backoff_seconds * 2 ** (n - 1), maximum_backoff_seconds)`

There is no sleep, randomness, or hidden jitter. The orchestration layer owns
when and how a returned delay is applied.

## Replay and concurrency

Given a durable run for the same idempotency key:

- no run → `START_NEW`;
- `CREATED` → `RESUME_CREATED`;
- `RUNNING` → `IN_FLIGHT`;
- any terminal state → `REUSE_TERMINAL`.

The persistence/orchestration layer remains responsible for atomic claiming;
these helpers only make the decision deterministic from the observed state.
