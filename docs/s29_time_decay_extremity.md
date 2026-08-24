# S29 — Time-Decay Extremity Entry

## Family
`window-timing`

## Concept
In the final seconds, buy the cheaper side when time decay has pushed its ask
to an extreme low.  The trade profits if the underdog outcome occurs, while the
low ask limits maximum loss.

## Rules
1. Consider snapshots with `rem_sec` in `[t_min, t_entry]` (default 1–10s left).
2. Pick whichever of YES/NO has the lower best ask.
3. Require that ask `<= ask_max` (default 0.20).
4. Refuse the trade if spot strongly disagrees with the chosen side:
   - do not buy YES if `delta_pct < -delta_buffer`
   - do not buy NO if `delta_pct > delta_buffer`
5. Confirm with a short spot TWAP on the same side of strike.
6. Hold to resolution.

## Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `t_entry` | 10.0 | Target seconds remaining. |
| `t_min` | 1.0 | Minimum seconds remaining. |
| `ask_max` | 0.20 | Maximum best ask of the cheaper side. |
| `delta_buffer` | 0.0002 | Maximum spot deviation allowed against the trade. |
| `twap_window` | 20 | Snapshots used for spot TWAP confirmation. |

## Proxies / Limitations
- Spot TWAP is used as a Chainlink/oracle proxy.
- Uses best ask only; very cheap asks may reflect wide spreads or stale data.
