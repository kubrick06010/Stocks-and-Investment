# Wave E3 deterministic research-automation contracts

Wave E3 is a control plane over the validated research pipeline. It is not a
second calculation engine. A versioned `ResearchAutomationDefinition` selects
an existing strategy and universe family, a dated `AutomationTrigger` records
why work became due, and an `AutomationRun` records exactly which persisted
artifacts each step consumed and produced.

The same definition version and trigger deduplication key form an idempotent
execution identity. Retries are explicit and limited to typed failure kinds.
Partial and failed executions remain visible; automation never silently falls
back to latest data, a current universe or another strategy version.

## Information barrier

`AutomationTrigger.as_of` is the research clock. Filing triggers must reference
the immutable filing artifact whose `available_at` caused the trigger. Outcome
artifacts are not valid inputs to research/thesis/watchlist steps. Existing PIT
views remain authoritative.

## V1 boundary

V1 supports manual, externally scheduled and filing-available triggers. It does
not include a daemon, distributed queue, notification system, live polling or a
new provider abstraction.
