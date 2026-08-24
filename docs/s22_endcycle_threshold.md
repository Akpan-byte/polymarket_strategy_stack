# S22 — Endcycle Threshold Sniper

## Family
`window-timing`

## Concept
Wait until the final seconds of a 5-minute prediction window (the "endcycle")
and "snipe" the leading side when the market has not yet fully priced in an
obvious directional outcome.

## Rules
1. Consider snapshots with `rem_sec` in `[t_min, t_entry]` (default 2–8s left).
2. Require `|delta_pct| >= delta_min` so the spot is clearly above/below strike.
3. Determine side: YES if `delta_pct > 0`, otherwise NO.
4. Require the leading-side best ask to be `<= ask_max` (default 0.85).  The
   cheaper the ask, the larger the edge if the outcome is already obvious.
5. Confirm with a short spot TWAP (Chainlink proxy): the TWAP must lie on the
   same side of strike as the current spot.
6. Hold to resolution (`exit_idx=None`).

## Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `t_entry` | 8.0 | Target seconds remaining to look for entry. |
| `t_min` | 2.0 | Minimum seconds remaining (avoids too-late fills). |
| `delta_min` | 0.0003 | Minimum absolute spot-strike move (0.03%). |
| `ask_max` | 0.85 | Maximum best ask of the leading side. |
| `twap_window` | 30 | Snapshots used for spot TWAP confirmation. |

## Proxies / Limitations
- Uses spot TWAP as a proxy for an external oracle / Chainlink reference.
- Uses best ask only; no deeper order-book fill simulation.
