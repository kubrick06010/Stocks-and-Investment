# Reporting and CLI methodology

Wave D reports are presentation products built exclusively from persisted
research artifacts. Reporting code does not fetch providers, calculate
metrics, or rerun historical strategies.

Every report preserves source references for the major sections. Historical
research is represented by sections with `section_type="research"`; later
measurements are represented by `section_type="outcome"`. This distinction is
preserved in the domain report, JSON, Markdown, and CLI output.

The historical stock report is assembled from persisted thesis snapshots,
change events, watchlist entries, monitoring events, and research outcomes.
An empty or missing history is rendered as an explicit empty report. Expected
CLI input errors use argparse diagnostics and do not expose analytical
tracebacks.

The CLI is read-only for historical commands. It consumes SQLiteStorage
records and never silently refreshes providers or recomputes historical
research.
