# Wave E4 persistence plan

Persist construction policies, requests and results additively in SQLite v10.
Targets, trades and constraint evaluations are bounded structured children of
the immutable result. References point to exact ResearchRuns/ResearchResults.

Do not persist derived reports. Do not convert targets into ledger transactions
without an explicit later user action. Migration must preserve schema v9 data,
be repeatable and survive close/reopen.
