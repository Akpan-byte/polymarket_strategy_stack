# S33 — MACD + RSI + VWAP Stack

## Concept
A three-indicator confirmation stack: MACD, RSI, and VWAP must all align in
the same direction before entry.  The idea is to avoid false breakouts by
requiring momentum (MACD), strength but not exhaustion (RSI), and price
position relative to a fair-value anchor (VWAP) to agree.

## Entry Rules
1. Warm up using the longest of `macd_slow`, `rsi_window`, and `vwap_window_sec`.
2. For each snapshot `idx` after warm-up:
   - Compute `delta_pct[idx]`; require `|delta| >= min_delta`.
   - Side = "YES" if delta > 0, else "NO".
3. MACD confirmation for the chosen side:
   - Compute EMA(fast) and EMA(slow) of the token price.
   - `macd_line = ema_fast - ema_slow`.
   - `signal_line = EMA(macd_line, macd_signal)`.
   - `hist = macd_line - signal_line`.
   - YES requires `hist[idx] > 0`; NO requires `hist[idx] < 0`.
4. RSI confirmation:
   - Compute Wilder's RSI of the token price over `rsi_window`.
   - YES requires `50 <= rsi <= rsi_high`.
   - NO requires `rsi_low <= rsi <= 50`.
5. VWAP/TWAP confirmation:
   - Because raw volume is unavailable, a rolling time-weighted average price
     (TWAP) of the token price is used as a VWAP proxy.
   - YES requires `price > twap`; NO requires `price < twap`.
6. Entry ask must be available and `<= max_price`.
7. Return the first qualifying snapshot as a hold-to-resolution signal.

## Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `macd_fast` | 12 | Fast EMA period for MACD. |
| `macd_slow` | 26 | Slow EMA period for MACD. |
| `macd_signal` | 9 | Signal EMA period for MACD. |
| `rsi_window` | 14 | RSI lookback window. |
| `rsi_low` | 40 | Lower RSI bound (NO side). |
| `rsi_high` | 60 | Upper RSI bound (YES side). |
| `vwap_window_sec` | 60 | Rolling TWAP window in seconds. |
| `min_delta` | 0.0002 | Minimum spot-strike delta required. |
| `max_price` | 0.75 | Do not enter if the ask is above this price. |

## Data Proxies / Limitations
- VWAP is approximated by a rolling time-weighted average price because the
  `Market` object does not include trade volume.
- Entry is at the best ask of the chosen side; exit is at resolution.
