# S54 Tick Acceleration + Spread-Compression Timing Entry

## Family
Momentum / microstructure

## Idea
When the order-book spread on the leading side compresses while spot velocity is
accelerating, the market is about to make a directional push. Enter before the
move has already consumed half of its expected range.

## Entry rules
1. **Arm** when `|delta_pct| >= min_delta`. Side is `YES` if delta is positive,
   otherwise `NO`.
2. Track the chosen side's spread `ask - bid` over a rolling `window`.
3. **Cancel** the armed state if spread widens past the `spread_cancel_pct`
   percentile of the window.
4. **Fire** when all of the following hold:
   - spread <= `spread_compress_pct` percentile of the window,
   - spot velocity has risen for `velocity_rise_ticks` consecutive ticks,
   - `move_used = |delta_pct| / max(|delta_pct| over the window)` is below
     `move_used_threshold`.
5. Entry price is the best ask of the chosen side and must be `<= max_price`.

## Parameters
| Parameter             | Default | Description                                             |
|-----------------------|---------|---------------------------------------------------------|
| `window`              | 30      | Rolling window for spread percentiles and expected move |
| `min_delta`           | 0.0002  | Minimum `|delta_pct|` required to arm                   |
| `spread_compress_pct` | 0.25    | Spread percentile threshold for entry (e.g. 25th)       |
| `spread_cancel_pct`   | 0.60    | Spread percentile threshold that cancels the setup      |
| `velocity_rise_ticks` | 3       | Consecutive ticks velocity must rise                    |
| `move_used_threshold` | 0.50    | Maximum allowed `move_used` ratio                       |
| `max_price`           | 0.70    | Maximum ask price allowed for entry                     |

## Exits
The strategy holds to window resolution (`exit_idx=None`).

## Limitations / proxies
- Spread is proxied by top-of-book `ask - bid` for the chosen side; depth beyond
  the best level is not available.
- "Expected move" is approximated by the rolling standard deviation of
  `delta_pct`; it is not a formal options-market expected move.
- Velocity is computed from spot changes per elapsed second; timestamp spacing
  is assumed to be roughly uniform.
