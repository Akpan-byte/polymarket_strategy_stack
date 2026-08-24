# S35 — 5m Lead for 15m Entry

## Concept
Use the early part of the window as a directional "lead".  If the token moves
strongly during that lead period and the move is confirmed by a short follow-
through window, enter for the remainder of the window.  The original framing
("5m lead for 15m entry") is adapted to the 5-minute BTC window data: the lead
is the initial segment of the current window and the position is held to
resolution.

## Entry Rules
1. Determine the snapshot `lead_idx` closest to `lead_sec` elapsed.
2. For the chosen side's token price series:
   - `lead_move = price[lead_idx] - price[0]`.
   - Require `|lead_move| >= min_lead_move`.
   - Side = "YES" if lead_move > 0, else "NO".
3. Search the confirmation window from `lead_idx + 1` to
   `lead_idx + confirm_sec`:
   - At snapshot `idx`, require `|delta_pct[idx]| >= min_delta` and the sign
     agrees with the chosen side.
   - `confirm_move = price[idx] - price[lead_idx]`.
   - YES requires `confirm_move >= min_confirm_move`.
   - NO requires `confirm_move <= -min_confirm_move`.
4. Entry ask must be available and `<= max_price`.
5. Return the first qualifying confirmation snapshot as a hold-to-resolution
   signal.

## Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `lead_sec` | 120 | Length of the initial lead period in seconds. |
| `confirm_sec` | 60 | Maximum length of the confirmation follow-through window. |
| `min_lead_move` | 0.015 | Minimum price move required during the lead period. |
| `min_confirm_move` | 0.005 | Minimum additional follow-through move required. |
| `min_delta` | 0.0003 | Minimum spot-strike delta at entry. |
| `max_price` | 0.75 | Do not enter if the ask is above this price. |

## Data Proxies / Limitations
- The strategy operates within a single 5-minute window; the "15m entry" label
  refers to the intended holding horizon from the original research context,
  which here maps to holding until window resolution.
- Entry is at the best ask of the chosen side; exit is at resolution.
