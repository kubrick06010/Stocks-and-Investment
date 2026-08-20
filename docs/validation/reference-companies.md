# Golden validation set

Wave B uses two deterministic accounting profiles rather than downloading mutable vendor data during ordinary tests:

| Profile | Purpose |
|---|---|
| ACME Synthetic Holdings | profitable, cash-generating company with debt, equity, goodwill-like book-value complexity, and positive returns |
| LOSS Synthetic Industries | loss-making, negative-equity, high-debt company with negative cash flow |

The profiles are deliberately small and transparent. Their values and hand calculations are stored in `tests/fixtures/financial/`. They are not investment recommendations and do not represent actual issuers. A later validation wave may add dated SEC-backed examples for real companies, but those must preserve filing/accessibility metadata and independent calculations.
