# S55 — Rapid Probability Change Chase

## Family
microstructure-exits

## Source
IndieHackers rapid-probability-change tell and kalshi-mcp-bot momentum-mode
exit discipline.

## Concept
When the token price moves fast (>= 4¢ in ~10s), someone is repricing the
outcome with size.  This strategy chases only the early leg of that move,
entering while price is still within 6¢ of the move's origin, and uses a tight
invalidation if the move fails to continue.

## Entry Rules
1. Compute the token-price change over the last `chase_window` ticks (the
"move").
2. Alert fires if `|change| >= alert_thresh` and the sign agrees with spot
delta.
3. Enter only if the current price is within `origin_slop` of the move origin
(starting price of the window).
4. Do not enter in the final 60 seconds of the window.
5. Entry ask must be available and `<= max_price`.

## Exit Rules
The first triggered condition sets `exit_idx`:
1. **Profit target**: best bid reaches entry ask + `take_profit`.
2. **Counter-tick invalidation**: a single tick moves against the position by
`counter_tick_exit` or more.
3. **Origin breach**: price returns to or beyond the move origin.
4. **Expiry safety**: fewer than 1 second remains.
5. **Hard time stop**: `max_hold_ticks` elapsed.

## Parameters
- `chase_window` (int): ticks defining the rapid-move window.
- `alert_thresh` (float): minimum price change to alert (default 0.04).
- `origin_slop` (float): maximum distance from move origin still allowed for
entry (default 0.06).
- `counter_tick_exit` (float): adverse single-tick move that invalidates the
chase (default 0.02).
- `take_profit` (float): best-bid gain target (midpoint of 5-8¢ range).
- `min_delta` (float): minimum absolute spot delta.
- `max_price` (float): maximum entry ask allowed.
- `max_hold_ticks` (int): longest allowed open duration.

## Data Proxies / Limitations
- The strategy uses token price as the probability proxy (the Market object has
no separate probability field).
- "Single tick" is a snapshot-to-snapshot change; if snapshot spacing is not
1 second, the per-tick velocity is still evaluated directly.
- Entry uses only data at or before `entry_idx`.
