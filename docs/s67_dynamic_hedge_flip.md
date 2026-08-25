# S67 Dynamic Hedge-Flip on Loss Signals

## Family
Directional / dynamic hedge

## Idea
Once a market has developed a directional move, enter with the move. If the
position immediately goes underwater and the adverse move is accompanied by a
velocity spike, exit the initial position and flip to the opposite side. If the
original direction later reclaims part of the loss, unwind the hedge. Only one
flip is allowed per market window.

## Entry rules
1. Wait until `elapsed_sec >= entry_delay_sec`.
2. Require `abs(delta_pct[idx]) >= min_delta`.
3. Take the directional side: **YES** if `delta_pct > 0`, otherwise **NO**.
4. Entry price must be the best ask of the chosen side and `<= max_price`.

## Flip trigger
After entry, scan forward and trigger a flip when:
- Adverse move (vs. entry best ask) is `>= adverse_pct`, and
- Current absolute delta velocity is `>= volume_mult *` the rolling median
  velocity baseline over the prior `vel_window` snapshots.

The flip exits the original position and enters the opposite side at the
opposite-side best ask.

## Unwind rule
If the original-side price later retraces `reclaim_frac` of the adverse
distance, exit the flipped position at the original-side best bid. If no unwind
occurs, the flipped position holds to window resolution.

## Parameters
| Parameter        | Default | Description                                              |
|------------------|---------|----------------------------------------------------------|
| `entry_delay_sec`| 60.0    | Seconds to wait before considering an entry              |
| `min_delta`      | 0.0005  | Minimum `abs(delta_pct)` required to enter (0.05%)       |
| `adverse_pct`    | 0.01    | Adverse move fraction needed to trigger a flip (1%)      |
| `vel_window`     | 5       | Snapshots used for velocity and baseline windows         |
| `volume_mult`    | 2.0     | Velocity multiplier required relative to baseline        |
| `reclaim_frac`   | 0.5     | Fraction of the adverse distance that triggers unwind    |
| `max_price`      | 0.70    | Maximum ask price allowed for entry or flip              |

## Exits
- The initial directional trade exits at the flip index.
- The flipped trade exits at the unwind index, or holds to resolution.

## Limitations / proxies
- No true volume data exists; "volume" velocity is approximated from the speed
  of `delta_pct` changes.
- Order-book depth beyond best bid/ask is not available.
- The strategy scans the realized path to find the first flip and unwind; in
  live trading these decisions would be made incrementally at each new snapshot.
