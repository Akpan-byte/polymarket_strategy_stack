# S24 — TWAP Reversal

## Family
`window-timing`

## Concept
Mean-reversion trade around a recent spot TWAP.  When live spot overextends
away from its TWAP (a proxy for a slower Chainlink oracle), buy the underdog
side expecting spot to revert before the window expires.

## Rules
1. Scan snapshots after enough history is available (`twap_window + vol_window`).
2. Require `rem_sec >= min_rem` so there is time for reversion.
3. Compute `TWAP = mean(spot[idx-twap_window:idx+1])`.
4. Compute realized volatility from `vol_window` returns and form a z-score:
   `z = (spot - TWAP) / strike / sigma`.
5. Require `|z| >= z_min`.
6. Take the contrarian side: buy NO if `z > 0` (spot overbought), buy YES if
   `z < 0` (spot oversold).
7. Require the chosen side's best ask `<= max_price`.
8. Hold to resolution.

## Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `twap_window` | 60 | Snapshots used for spot TWAP. |
| `z_min` | 1.0 | Minimum absolute z-score to enter. |
| `max_price` | 0.45 | Maximum best ask of the contrarian side. |
| `min_rem` | 15.0 | Minimum seconds remaining at entry. |
| `vol_window` | 30 | Snapshots used for realized volatility. |

## Proxies / Limitations
- Spot TWAP stands in for a slower external oracle.
- Uses best ask only; no order-book depth for fill quality.
