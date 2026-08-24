# S32 — MOMENTUM Mode

## Concept
Enter a directional position when the token is in a clear momentum state:
price velocity over a lookback window is strong, directionally aligned with the
spot-strike delta, and the last few ticks have persisted in the same direction.
The strategy avoids choppy/ranging windows by requiring sustained directional
ticks rather than a single spike.

## Entry Rules
1. Skip the first `vel_window + sustain_ticks` snapshots and the last 5.
2. At snapshot `idx`, compute `delta_pct[idx]`.
   - If `|delta_pct| < min_delta`, skip.
   - Side = "YES" if delta > 0, else "NO".
3. Compute token velocity over `vel_window` for the chosen side.
   - `vel = price[idx] - price[idx - vel_window]`.
   - Require `|vel| >= min_vel` and `sign(vel) == sign(delta)`.
4. Require sustained directional ticks: over the last `sustain_ticks`, the
   chosen side must have moved favorably on every tick.
5. Entry ask must be available and `<= max_price`.
6. Return the first qualifying snapshot as a hold-to-resolution signal.

## Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `vel_window` | 6 | Lookback window for velocity measurement. |
| `min_vel` | 0.015 | Minimum token price velocity required. |
| `min_delta` | 0.0003 | Minimum spot-strike delta required. |
| `max_price` | 0.75 | Do not enter if the ask is above this price. |
| `sustain_ticks` | 3 | Number of recent ticks that must move in the trade direction. |

## Data Proxies / Limitations
- Token velocity is computed from `price_up` / `price_down`, which are the last
trade/mark prices.  No true volume or tick count is available, so "sustained
ticks" uses consecutive snapshot differences.
- Entry is at the best ask of the chosen side; exit is at resolution.
