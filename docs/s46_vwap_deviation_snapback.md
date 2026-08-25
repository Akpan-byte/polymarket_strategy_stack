# S46 VWAP Deviation Snap-Back

## Family
Mean reversion

## Idea
Spot can overextend away from the session VWAP and then snap back. This
strategy enters against the deviation once it is statistically extended and
the move is losing velocity, while vetoing entries that look like true
breakouts.

## Entry rules
1. Compute a rolling session VWAP proxy (time-weighted average of `spot` over
   `vwap_window_sec`) and 1-minute rolling standard-deviation bands.
2. Compute the z-score deviation: `(spot - vwap) / sigma`.
3. Require `|deviation| >= entry_dev`, `rem_sec >= min_rem`, and the chosen
   side's best ask `<= max_price`.
4. Require velocity (absolute change in `delta_pct`) to have decayed by at
   least `velocity_decay_pct` from its recent peak over
   `velocity_peak_window` snapshots.
5. **Breakout veto**: skip the entry if `|deviation| >= breakout_dev` and
   velocity is rising (`velocity[idx] > velocity[idx-1]`).
6. Enter **YES** when deviation is negative (spot below VWAP), **NO** when
   deviation is positive (spot above VWAP).

## Parameters
| Parameter              | Default | Description                                          |
|------------------------|---------|------------------------------------------------------|
| `vwap_window_sec`      | 14400.0 | VWAP lookback in seconds (4h; full session proxy)    |
| `sigma_window_sec`     | 60.0    | Rolling std window for sigma bands in seconds        |
| `entry_dev`            | 1.5     | Minimum |deviation| for entry                            |
| `exit_dev`             | 0.5     | Deviation threshold to take profit                   |
| `breakout_dev`         | 2.5     | Deviation threshold for breakout veto                |
| `velocity_peak_window` | 10      | Snapshots used to find the recent velocity peak      |
| `velocity_decay_pct`   | 0.5     | Required velocity decay from peak (0.5 = 50%)        |
| `min_sigma`            | 1e-6    | Floor for sigma to avoid divide-by-zero              |
| `min_rem`              | 120.0   | Minimum seconds remaining to enter                   |
| `final_min_rem`        | 60.0    | In the final minute, hold to resolution              |
| `max_price`            | 0.55    | Maximum ask price allowed for entry                  |

## Exits
The strategy exits when the absolute deviation returns inside `exit_dev`.
If that condition occurs in the final `final_min_rem` seconds, the position is
held to window resolution instead.

## Limitations / proxies
- True trade-volume VWAP is unavailable; this implementation uses a time-
  weighted average of `spot` as a VWAP proxy.
- The 1-minute sigma bands use a rolling standard deviation of spot rather
  than realized 1-minute volatility.
- Velocity is approximated by the snapshot-to-snapshot change in `delta_pct`.
