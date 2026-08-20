# Backtest cost model

The multi-period simulator charges `transaction_cost_rate` on actual traded
notional. Traded notional counts buys plus sells. Turnover is traded notional
divided by pre-trade portfolio value, so a complete replacement has turnover
1.0. This differs from the alternative `0.5 * sum(abs(weight changes))`
convention and is intentional. Costs are deducted before target positions are
formed, preventing negative cash or hidden leverage.
