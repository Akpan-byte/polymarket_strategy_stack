# S66 — 7-Trigger Exit Stack

## Family
microstructure-exits

## Source
kalshi-mcp-bot exit manager priority order.

## Concept
The strategy enters on a simple momentum/delta alignment, then manages the
trade with a priority-ordered stack of seven exit triggers.  The first trigger
that fires sets `exit_idx`.  The stack is designed to handle distinct failure
modes: take-profit, stop-loss, gap protection, velocity reversal, trailing
stop, time-decay floor, and model invalidation.

## Entry Rules
1. Spot delta at `idx` is at least `min_delta` and fixes the side
(`YES` if positive, `NO` if negative).
2. Token price velocity over `vel_window` ticks is at least `min_vel` and
agrees with delta.
3. Entry ask is available and `<= max_price`.

## Exit Rules
Evaluated in priority order after entry; the first match wins:
1. **Take profit**: unrealized gain >= 45% of max payout `(1.00 - entry_price)`.
2. **Stop loss**: adverse move >= `sl_calm` in calm regime or `sl_volatile` in
volatile regime.  Volatility is proxied by the standard deviation of recent
spot returns (threshold 0.03%).
3. **Velocity spike**: a single tick moves against the trade at >= `vel_spike`
per second.
4. **Velocity reversal**: 3 consecutive counter-ticks while the position is
profitable.
5. **Trailing stop**: price retreats from the best seen level by `trail_low`
(for entries below $0.50) or `trail_high` (for entries at/above $0.50).
6. **Time floor**: minimum acceptable unrealized PnL ratchets up as the window
closes:
   - T-120s to T-60s: require >= 30% of max payout.
   - T-60s or less: require >= 15% of max payout.
7. **Model/delta flip**: spot delta sign reverses from the entry sign.

If none of the above fire, the position is closed at the hard time stop or
just before expiry.

## Parameters
- `vel_window` (int): lookback ticks for entry velocity.
- `min_delta` (float): minimum absolute spot delta.
- `min_vel` (float): minimum token price velocity for entry.
- `max_price` (float): maximum entry ask allowed.
- `sl_calm` (float): stop-loss width in calm regime.
- `sl_volatile` (float): stop-loss width in volatile regime.
- `vel_spike` (float): adverse per-second velocity that triggers gap protection.
- `trail_low` (float): trailing-stop retreat for low entry prices.
- `trail_high` (float): trailing-stop retreat for high entry prices.
- `max_hold_ticks` (int): longest allowed open duration.

## Data Proxies / Limitations
- Regime detection is a simple volatility threshold on recent spot returns.
- The "NN/model flip" trigger is proxied by a spot-delta sign reversal.
- Per-second velocity assumes snapshot timestamps are accurate; it is computed
as price change divided by elapsed seconds between snapshots.
- Entry uses only data at or before `entry_idx`.
