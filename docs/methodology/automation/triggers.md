# E3A Trigger Construction

E3A constructs immutable `AutomationTrigger` records. It does not execute an
automation definition, start a daemon, fetch providers, or mutate evidence.

## Time and replay

All trigger builders receive an injected, timezone-aware UTC `observed_at`.
Manual and scheduled identities include the definition/version and the
research observation minute/date. Replaying the same inputs therefore returns
the same trigger ID and deduplication key.

The `as_of` date is the research information date. The domain contract also
ensures a trigger cannot make information available before its observation
time.

## Manual triggers

`build_manual_trigger` creates one trigger only when the definition is enabled
and explicitly allows `manual`. Manual requests are not inferred from wall
clock state.

## Scheduled triggers

`ScheduledTriggerSource` is a deterministic due check, not a scheduler. V1
accepts five UTC cron fields with `*`, comma-separated integers, and ascending
ranges; day-of-week follows cron's Sunday=0 convention. A trigger is due only
when all fields match the UTC minute containing
`observed_at`; there is no implicit catch-up or time-zone conversion.

## Filing triggers

`FilingTriggerSource` accepts a persistence reader implementing
`load_filings_available_on`. It never accepts a provider. Returned documents
are filtered again using the exact timestamp rule
`filing.available_at <= observed_at`, which protects against coarse date-only
storage readers. Documents are deduplicated by stable filing ID and sorted by
`(ticker, available_at, filing ID)`. Each filing creates its own trigger so a
later filing cannot mutate an earlier delivery's identity.

An empty persisted filing set produces no trigger. A future filing physically
present in storage is excluded until its `available_at` is observed. The
deduplication key includes the filing ID and definition identity/version, so a
newly available filing produces a distinct trigger without changing an earlier
one.

## Deliberate limits

This module does not implement cron catch-up, persistence of deduplication
state, concurrency control, retries, or a background daemon. Those belong to a
future orchestrator and must consume these deterministic trigger records.
