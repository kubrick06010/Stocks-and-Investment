# Wave E5 local interactive research contracts

`ResearchViewRequest` freezes the requested view, methodology version, stable
artifact identities, as-of date, factor version, horizon, outcome visibility
and result limit. It contains no raw SQL, provider selection, arbitrary file
path, sort expression or executable query language.

`ResearchView` returns an existing structured `ResearchReport`, explicit status,
navigation links, warnings and deduplicated source lineage. A valid view cannot
exist without a report; a missing/invalid request cannot smuggle one.

`OutcomeVisibility.EXCLUDE` is the default. `SEPARATE` may include persisted
post-hoc outcomes, but only through report sections whose type remains
`outcome`. No view may flatten future outcomes into historical research.

`InteractiveResearchService` is provider-independent. Its implementation reads
persisted evidence and invokes existing deterministic report/comparison/
efficacy services; it does not calculate financial metrics or refresh data.

V1 is a local terminal interface with no network listener. Database selection
and safe rendering are edge concerns, but their behavior is release-gated.
