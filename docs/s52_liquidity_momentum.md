# S52 — Liquidity Momentum

## Family
microstructure-exits

## Source
Benjam1nCup "5min BTC Liquidity Momentum Arbitrage Bot" — directional
Buy1 signal (the complementary arbitrage leg is excluded per project
constraints).

## Concept
Detect a sudden shift in order-book buying/selling pressure via an influence
metric, then confirm that the pressure direction matches the live spot-vs-strike
delta before entering.  The exit is microstructure-driven: close when the
influence decays back to zero or a hard time stop hits.

## Entry Rules
1. Compute a per-tick influence proxy from top-of-book changes and token-price
movement.  A signed pressure value is positive when bids rise / asks are lifted
and the token price moves up; the reverse is negative.  Large single-tick moves
get double sweep weight.
2. For each candidate snapshot, sum influence over the last `infl_window` ticks.
3. Trigger only when the summed influence exceeds the running `percentile`
threshold of absolute influence observed so far in the market.
4. Confirm `sign(influence) == sign(spot - strike)` and `|delta_pct| >= min_delta`.
5. Entry ask must be available and `<= max_price`.

## Exit Rules
The first condition that fires sets `exit_idx`:
1. **Influence decay**: the rolling `infl_window` influence collapses to (near)
zero.
2. **Expiry safety**: fewer than 1 second remains.
3. **Hard time stop**: `max_hold_ticks` elapsed.

## Parameters
- `infl_window` (int): ticks over which influence is summed.
- `percentile` (float): running percentile threshold for trigger (e.g., 0.95).
- `min_delta` (float): minimum absolute spot delta to confirm direction.
- `max_price` (float): maximum entry ask allowed.
- `max_hold_ticks` (int): longest allowed open duration in snapshots.

## Data Proxies / Limitations
- Full Level-2 event data (bid/ask adds, pulls, sweeps, sizes by level) is not
available in the `Market` object, so influence is proxied from best-bid/ask
migration and token-price velocity.
- The running percentile is computed within the current market only; cross-market
history is not retained.
- Entry uses only information at or before `entry_idx`.
