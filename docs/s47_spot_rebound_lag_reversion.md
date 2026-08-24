# S47 Spot-Rebound Lag Reversion

## Family
Mean reversion

## Idea
Spot occasionally overextends and then snaps back well before the token price
fully reflects the reversal. This strategy enters against the original move
once the spot has reversed by a fixed amount from a recent extreme, using a
short spot TWAP as a synthetic oracle to confirm the rebound is real.

## Entry rules
1. Look back `lookback_window` snapshots from the current bar.
2. **Up move then rebound**: if the maximum `delta_pct` in that window is at
   least `trigger_pct` and the current `delta_pct` has fallen at least
   `rebound_pct` below that maximum, and the short TWAP of `delta_pct` is above
   the current value, enter **NO**.
3. **Down move then rebound**: if the minimum `delta_pct` in that window is at
   most `-trigger_pct` and the current `delta_pct` has risen at least
   `rebound_pct` above that minimum, and the short TWAP is below the current
   value, enter **YES**.
4. Entry price must be the best ask of the chosen side and `<= max_price`.

## Parameters
| Parameter        | Default | Description                                     |
|------------------|---------|-------------------------------------------------|
| `lookback_window`| 20      | Snapshots used to find the recent extreme       |
| `trigger_pct`    | 0.0015  | Minimum spot excursion required (0.15%)         |
| `rebound_pct`    | 0.0010  | Required reversal from that extreme             |
| `twap_window`    | 5       | Snapshots used for the confirming spot-TWAP     |
| `max_price`      | 0.70    | Maximum ask price allowed for entry             |

## Exits
The strategy holds to window resolution (`exit_idx=None`).

## Limitations / proxies
- The "token lag" is inferred from the spot rebound rather than measured with
  order-book depth; best bid/ask are the only book data used.
- A short spot TWAP substitutes for an external oracle feed.
