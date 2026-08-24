# S48 Velocity-Flip Reversal

## Family
Mean reversion

## Idea
When spot velocity is strong in one direction and then flips hard in the other,
the move is often exhausted. This strategy fades the pre-flip direction once
the rolling velocity crosses from strongly positive to strongly negative (or
vice versa).

## Entry rules
1. Compute two adjacent spot-delta velocities over `vel_window` snapshots:
   - `prior` = `delta_pct[idx-vel_window] - delta_pct[idx-2*vel_window]`
   - `current` = `delta_pct[idx] - delta_pct[idx-vel_window]`
2. **Up exhaust**: if `prior > pre_threshold` and `current < -post_threshold`,
   enter **NO**.
3. **Down exhaust**: if `prior < -pre_threshold` and `current > post_threshold`,
   enter **YES**.
4. Entry price must be the best ask of the chosen side and `<= max_price`.

## Parameters
| Parameter        | Default | Description                                     |
|------------------|---------|-------------------------------------------------|
| `vel_window`     | 5       | Snapshots used for each velocity measurement    |
| `pre_threshold`  | 0.0005  | Minimum pre-flip velocity magnitude (0.05%)     |
| `post_threshold` | 0.0003  | Minimum post-flip velocity magnitude (0.03%)    |
| `max_price`      | 0.70    | Maximum ask price allowed for entry             |

## Exits
The engine holds the position to window resolution.

## Limitations / proxies
- Velocity is derived from spot `delta_pct` only.
- No order-book depth beyond best bid/ask is used.
