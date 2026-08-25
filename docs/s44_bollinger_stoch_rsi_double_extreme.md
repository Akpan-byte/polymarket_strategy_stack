# S44 Bollinger + Stochastic RSI Double-Extreme

## Family
Mean reversion

## Idea
A price extreme at a Bollinger Band combined with a Stochastic RSI crossover
leaving an extreme zone flags a short-term reversal. The strategy buys YES when
spot is at the lower band and Stoch-RSI crosses up out of oversold territory,
and buys NO when spot is at the upper band and Stoch-RSI crosses down out of
overbought territory.

## Entry rules
1. Compute Bollinger Bands on `spot` using `bb_window` and `bb_std` standard
   deviations (population std).
2. Compute RSI on spot returns using `rsi_window`.
3. Compute Stochastic RSI: normalize RSI over `stoch_window`, then smooth with
   `%K = SMA(stoch_rsi, k_period)` and `%D = SMA(%K, d_period)`.
4. **Oversold long**: if `spot[idx] <= lower_band`, `%K[idx-1] < %D[idx-1]`,
   `%K[idx] > %D[idx]`, and `%K[idx-1] < oversold`, enter **YES**.
5. **Overbought short**: if `spot[idx] >= upper_band`, `%K[idx-1] > %D[idx-1]`,
   `%K[idx] < %D[idx]`, and `%K[idx-1] > overbought`, enter **NO**.
6. Entry price must be the best ask of the chosen side and `<= max_price`.
7. Require at least `min_t_rem` seconds remaining in the window.
8. If `skip_expanding_bands` is true, skip entries when bands are expanding in
   the direction of the touch.

## Parameters
| Parameter            | Default | Description                                         |
|----------------------|---------|-----------------------------------------------------|
| `bb_window`          | 20      | Rolling window for Bollinger mean/std               |
| `bb_std`             | 2.0     | Standard-deviation multiplier for the bands         |
| `rsi_window`         | 14      | Window for RSI calculation                          |
| `stoch_window`       | 14      | Window for min/max normalization of RSI             |
| `k_period`           | 3       | SMA period for %K                                   |
| `d_period`           | 3       | SMA period for %D                                   |
| `oversold`           | 20.0    | Stoch-RSI level required for a YES entry            |
| `overbought`         | 80.0    | Stoch-RSI level required for a NO entry             |
| `max_price`          | 0.55    | Maximum ask price allowed for entry                 |
| `min_t_rem`          | 90.0    | Minimum seconds remaining at entry                  |
| `skip_expanding_bands`| True   | Skip entries when bands are widening                |

## Exits
The strategy holds to window resolution (`exit_idx=None`). The stated TP
(mid-band) and SL (new extreme beyond the trigger bar) are not implemented
because `generate_signals` is constrained to data at or before `entry_idx`.

## Limitations / proxies
- Stoch-RSI and Bollinger Bands are computed from spot only; token price is used
  only for the fill price and `max_price` filter.
- Order-book depth beyond best bid/ask is not available.
- Mid-band take-profit and beyond-extreme stop-loss require future data and are
  therefore omitted.
