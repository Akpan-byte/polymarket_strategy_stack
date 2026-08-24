# S43 Bollinger + RSI Reversal

## Family
Mean reversion

## Idea
Spot extremes relative to a rolling Bollinger Band, combined with an RSI
extreme, flag a short-term reversal in BTC's 5-minute binary window. The
strategy buys YES when spot is oversold and sells YES (buys NO) when spot is
overbought.

## Entry rules
1. Compute Bollinger Bands on `spot` using `bb_window` and `bb_std` standard
   deviations (population std).
2. Compute RSI on spot returns using `rsi_window`.
3. **Oversold long**: if `spot[idx] <= lower_band` and `rsi <= oversold`, enter
   **YES**.
4. **Overbought short**: if `spot[idx] >= upper_band` and `rsi >= overbought`,
   enter **NO**.
5. Entry price must be the best ask of the chosen side and `<= max_price`.

## Parameters
| Parameter      | Default | Description                                     |
|----------------|---------|-------------------------------------------------|
| `bb_window`    | 20      | Rolling window for Bollinger mean/std           |
| `bb_std`       | 2.0     | Standard-deviation multiplier for the bands     |
| `rsi_window`   | 14      | Window for RSI calculation                      |
| `oversold`     | 30.0    | RSI level required for a YES entry              |
| `overbought`   | 70.0    | RSI level required for a NO entry               |
| `max_price`    | 0.70    | Maximum ask price allowed for entry             |

## Exits
The strategy holds to window resolution (`exit_idx=None`).

## Limitations / proxies
- RSI and Bollinger Bands are computed from spot only; token price is used only
  for the fill price.
- Order-book depth beyond best bid/ask is not available.
