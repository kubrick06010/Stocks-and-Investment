# Narrative methodology

`structured_narrative_v1` serializes existing report sections in stable order,
preserving section types and source references. It does not infer facts or
calculate metrics. Research sections are included by default; post-hoc outcome
sections require an explicit policy flag and are marked separately.

`optional_llm_disabled_v1` is a safe, explicit no-op. It exists to make the
future extension point visible without making external inference a dependency.
