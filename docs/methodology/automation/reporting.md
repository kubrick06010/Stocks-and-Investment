# Automation-run reporting

Automation reporting is a read-only presentation adapter over the persisted
`AutomationRun` contract. It records the automation definition and trigger
when those already-loaded objects are supplied, and always reports the run's
own immutable IDs, versions, as-of date, status and step lineage.

Each step exposes its version, attempt, timing, input references and output
references. Failed steps retain their typed failure, message and retryable
flag. A partial run therefore remains inspectable instead of being presented
as a successful pipeline. Retries are evidence from the run; the report never
performs a retry.

The adapter does not query storage, call providers, execute an orchestrator or
derive research metrics. Missing optional definition/trigger context is
explicitly represented as unavailable. This makes a report safe to generate
after reopening a database from already-loaded historical records.

Reports use the shared `ResearchReport` and `ReportSection` contracts. JSON and
Markdown are delegated to the existing renderers; the compact text view is
only a presentation convenience. The report is an automation-control-plane
view, not an outcome evaluation: it has no outcome section and records
`outcome_information_included = false` in metadata.
