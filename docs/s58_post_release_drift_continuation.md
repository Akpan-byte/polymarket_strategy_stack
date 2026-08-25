# S58 — Post-Release Drift Continuation

## Family
Momentum / event drift

## Concept
After a decisive directional move immediately following a release, the spot
often pauses and pulls back before continuing to drift. This strategy waits
for that pullback to hold, then enters in the original drift direction while
the token price is still cheap.

## Rules
1. Measure the maximum move from strike inside `release_window_sec` after
   window start.
2. Require a decisive move: `|delta_pct| >= decisive_move_pct` (default 0.4%).
   If both directions qualify, take the larger-magnitude move.
3. Compute the pullback level as a `pullback_retrace_pct` retrace of the
   decisive move.
4. Wait for the spot to reach the pullback level, then hold at that level for
   at least `pullback_hold_sec` (default 2 minutes).
5. Enter the drift direction when the best ask of the chosen side is
   `<= max_entry_price` (default 0.55).
6. Allow up to `max_trades` drift entries per market (default 3).
7. Stop scanning if the spot crosses back through strike (window resolves
   against the drift).
8. Do not enter after `no_trade_after_sec` (default 60 minutes).

## Parameters
| Parameter              | Default | Description                                          |
|------------------------|---------|------------------------------------------------------|
| `release_window_sec`   | 60.0    | Seconds after start to detect the decisive move      |
| `decisive_move_pct`    | 0.004   | Minimum decisive spot move (0.4%)                    |
| `pullback_retrace_pct` | 0.25    | Fraction of the decisive move used for pullback level|
| `pullback_hold_sec`    | 120.0   | Minimum time pullback level must hold                |
| `max_entry_price`      | 0.55    | Maximum best ask allowed for entry                   |
| `max_trades`           | 3       | Maximum drift entries per market                     |
| `no_trade_after_sec`   | 3600.0  | Do not enter trades after this many seconds          |
| `stop_if_reverses`     | True    | Stop if spot crosses strike against the drift        |

## Exits
The strategy holds to window resolution (`exit_idx=None`).

## Proxies / Limitations
- "Release" time is proxied by the start of each 5-minute window; no external
  event calendar is used.
- Pullback detection uses spot only; token order-book prices are used only for
  fill prices.
- The 25% retrace and 2-minute hold are heuristics and may need tuning per
  release type.
