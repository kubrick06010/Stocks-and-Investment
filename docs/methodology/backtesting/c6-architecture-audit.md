# C6 architecture audit

The pre-closure simulator formed one top-N portfolio from an in-memory score
map and a single price window. It did not load persisted `ResearchRun` records,
did not model rebalance turnover, and persisted no `BacktestRun` lineage.

The audit found one release-blocking identity risk: ending prices were first
filtered and then paired with an unfiltered starting-price list. This was
replaced with ticker-keyed mappings and an adversarial middle-missing ticker
test.

Other observations:

- ResearchRun and ResearchResult persistence now retain universe/version,
  rankings, factor components and criteria; C6 must consume these records.
- Universe exits are decisions at rebalance dates, not daily liquidation rules.
- The existing portfolio ledger supports BUY/SELL/DIVIDEND/FEE/SPLIT, but the
  V1 backtest simulator uses a transparent security-keyed state and documents
  its narrower boundary.
- Price adjustment policies are explicit. Mixed policies are rejected.
- The former one-time entry haircut is not sufficient for multi-period C6;
  turnover-based notional costs are required.
