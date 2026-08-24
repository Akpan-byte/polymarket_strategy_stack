# S42 First-60s Fakeout Fade

## Family
Mean reversion

## Idea
BTC 5-minute Polymarket binaries often print an emotional spike or dump in the
opening seconds. This strategy fades that move once the spot price reverses by
a meaningful amount, using a short spot-TWAP as a Chainlink-style oracle proxy.

## Entry rules
1. Time window: only consider snapshots with `elapsed_sec <= 60`.
2. Look back from the open to the current snapshot for the maximum and minimum
   `delta_pct` (spot vs strike).
3. **Up fakeout**: if the running maximum `delta_pct` exceeds `fakeout_pct` and
   the current `delta_pct` has retraced at least `retrace_pct` from that maximum,
   and the short TWAP of `delta_pct` is above the current value (falling
   momentum), enter **NO**.
4. **Down fakeout**: if the running minimum `delta_pct` is below
   `-fakeout_pct` and the current `delta_pct` has bounced at least
   `retrace_pct` from that minimum, and the short TWAP is below the current
   value (rising momentum), enter **YES**.
5. Entry price must be the best ask of the chosen side and `<= max_price`.

## Parameters
| Parameter      | Default | Description                                     |
|----------------|---------|-------------------------------------------------|
| `fakeout_pct`  | 0.0010  | Minimum spot move away from strike (0.10%)      |
| `retrace_pct`  | 0.0005  | Required pullback from the fakeout extreme      |
| `twap_window`  | 5       | Snapshots used for the confirming spot-TWAP     |
| `max_price`    | 0.70    | Maximum ask price allowed for entry             |

## Exits
The strategy does not set an explicit `exit_idx`, so the engine holds the
position to window resolution.

## Limitations / proxies
- No true oracle feed is available; a short spot TWAP over recent snapshots
  acts as the Chainlink proxy.
- Order-book depth beyond best bid/ask is not used.
