# S25 — Momentum Snipe with Hedge

## Family
`window-timing`

## Concept
Snipe the leading side when token price momentum accelerates near the end of
the window.  The "hedge" is a residual-risk filter: require the opposite token
to still trade above a minimum ask, confirming the market has not fully
collapsed to certainty and leaving room for the momentum side to reprice.

## Rules
1. Consider snapshots with `rem_sec` in `[t_min, t_entry]` (default 4–20s left).
2. Compute token velocity over `vel_window` snapshots on the YES token.
3. Require `|velocity| >= min_vel`.
4. Determine side from velocity sign; require it to agree with `delta_pct`
   (no spot/token divergence).
5. Require the chosen side's best ask `<= max_price`.
6. **Hedge filter:** the opposite side's best ask must be `>= hedge_min`
   (default 0.10).  This ensures the market still prices meaningful residual
   probability, so the momentum side is not already at certainty.
7. Hold to resolution.

## Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `vel_window` | 6 | Snapshots for token velocity. |
| `min_vel` | 0.015 | Minimum absolute token price change. |
| `t_entry` | 20.0 | Target seconds remaining. |
| `t_min` | 4.0 | Minimum seconds remaining. |
| `max_price` | 0.75 | Maximum best ask of the momentum side. |
| `hedge_min` | 0.10 | Minimum best ask of the opposite side (hedge filter). |

## Proxies / Limitations
- "Hedge" is implemented as a residual-risk filter, not a true offsetting
  position, because the engine executes one signal at a time per market.
- Uses best bid/ask only.
