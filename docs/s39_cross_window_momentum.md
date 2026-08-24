# S39 — Cross-Window Momentum Continuation

## Concept
Require directional momentum to persist across two lookback windows (short and
long).  A trade fires only when both windows show aligned, above-threshold
momentum and the shorter-window momentum has not faded relative to the longer-
window move.  This filters spike-and-fade moves and keeps positions where
pressure is continuing.

## Entry Rules
1. Warm up using `long_window` snapshots; skip the last 5.
2. At snapshot `idx`:
   - Compute `delta_pct[idx]`; require `|delta| >= min_delta`.
   - Side = "YES" if delta > 0, else "NO".
3. For the chosen side's token price series:
   - `short_vel = price[idx] - price[idx - short_window]`.
   - `long_vel = price[idx] - price[idx - long_window]`.
   - Require `|short_vel| >= min_short_vel` and `|long_vel| >= min_long_vel`.
   - Require `sign(short_vel) == sign(long_vel) == sign(delta)`.
4. Continuation filter:
   - Require `|short_vel| >= continuation_ratio * |long_vel|`.
   - This ensures short-term momentum is not collapsing relative to the longer
     move.
5. Entry ask must be available and `<= max_price`.
6. Return the first qualifying snapshot as a hold-to-resolution signal.

## Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `short_window` | 5 | Short momentum lookback in snapshots. |
| `long_window` | 15 | Long momentum lookback in snapshots. |
| `min_short_vel` | 0.010 | Minimum short-window velocity. |
| `min_long_vel` | 0.015 | Minimum long-window velocity. |
| `continuation_ratio` | 0.50 | Minimum `|short_vel| / |long_vel|` allowed. |
| `min_delta` | 0.0002 | Minimum spot-strike delta required. |
| `max_price` | 0.75 | Do not enter if the ask is above this price. |

## Data Proxies / Limitations
- Momentum is measured from token last prices (`price_up` / `price_down`);
  there is no true volume or transaction tick data.
- Entry is at the best ask of the chosen side; exit is at resolution.
