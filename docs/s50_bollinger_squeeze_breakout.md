# S50 Band-Width Squeeze -> Expansion Breakout

## Family
Volatility breakout / momentum continuation

## Idea
When Bollinger bandwidth compresses to a trailing-window low, the market is
coiling. The first close outside the band, accompanied by a surge in spot
velocity, flags a directional breakout in BTC's 5-minute binary window.

## Entry rules
1. Compute Bollinger Bands on `spot` using `bb_window` and `bb_std` standard
   deviations (population std).
2. Compute bandwidth as `upper - lower`.
3. **Arm** when bandwidth <= `bandwidth_pctile` percentile of the trailing
   `bandwidth_window`.
4. **Trigger** when `spot[idx]` closes above `upper` or below `lower` AND
   spot velocity over `velocity_lookback` bars >= `velocity_multiplier` times
   the trailing mean velocity (`velocity_window`).
5. Enter the break direction (**YES** for upper break, **NO** for lower break)
   if the best ask of the chosen side is `<= max_price` and `rem_sec >= min_rem_sec`.
6. Disarm the squeeze after a trigger or after `max_squeeze_hours` with no
   trigger; one attempt per squeeze.

## Parameters
| Parameter          | Default | Description                                           |
|--------------------|---------|-------------------------------------------------------|
| `bb_window`        | 20      | Rolling window for Bollinger mean/std                 |
| `bb_std`           | 2.0     | Standard-deviation multiplier for the bands           |
| `bandwidth_window` | 60      | Trailing window for bandwidth percentile (bars)       |
| `bandwidth_pctile` | 20.0    | Percentile threshold that arms the squeeze            |
| `velocity_lookback`| 1       | Bars over which spot velocity is measured             |
| `velocity_window`  | 10      | Trailing window for mean velocity                     |
| `velocity_multiplier`| 1.5   | Velocity must exceed this multiple of mean velocity   |
| `max_price`        | 0.60    | Maximum ask price allowed for entry                   |
| `min_rem_sec`      | 90.0    | Minimum seconds remaining at entry                    |
| `max_squeeze_hours`| 6.0     | Max hours a squeeze can remain armed without trigger  |

## Exits
The strategy exits on a false break: the first bar after entry where `spot`
closes back inside the Bollinger Band. If that never happens, it holds to
window resolution (`exit_idx=None`).

## Limitations / proxies
- Bandwidth and velocity are computed from spot only; token price is used only
  for the fill price.
- The "volume surge" in the description is proxied by spot velocity because
  traded volume is not present in the market object.
- Order-book depth beyond best bid/ask is not available.
