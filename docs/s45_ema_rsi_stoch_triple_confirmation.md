# S45 — EMA5/EMA10 Cross + RSI + Stochastic Triple Confirmation

## Family
Trend / momentum confirmation

## Idea
Require three independent indicators to align in the same direction before
entering a BTC 5-minute binary window. The EMA cross identifies a fresh short-
term trend, RSI confirms directional strength without exhaustion, and the
stochastic oscillator confirms bounded momentum in the trade direction.

## Entry Rules
1. Warm up using the longest of `ema_slow`, `rsi_window`, and `stoch_k + stoch_d`.
2. For each snapshot `idx`:
   - Require `elapsed_sec[idx] <= max_elapsed_sec`.
   - Entry ask for the chosen side must be `<= max_price`.
3. EMA confirmation:
   - Compute EMA(`ema_fast`) and EMA(`ema_slow`) of `spot`.
   - YES requires a bullish cross within the last `cross_lookback` bars.
   - NO requires a bearish cross within the last `cross_lookback` bars.
4. RSI confirmation:
   - Compute Wilder's RSI of `spot` over `rsi_window`.
   - YES requires `rsi_yes_low <= rsi <= rsi_yes_high`.
   - NO requires `rsi_no_low <= rsi <= rsi_no_high`.
5. Stochastic confirmation:
   - Compute `%D` of the stochastic oscillator using rolling min/max of `spot`
     with `stoch_k` and `stoch_d`.
   - Value must be inside `[stoch_low, stoch_high]`.
   - YES requires `%D` to be rising versus the previous bar.
   - NO requires `%D` to be falling versus the previous bar.
6. Return the first qualifying snapshot.

## Parameters
| Parameter         | Default | Description                                      |
|-------------------|---------|--------------------------------------------------|
| `ema_fast`        | 5       | Fast EMA period                                  |
| `ema_slow`        | 10      | Slow EMA period                                  |
| `rsi_window`      | 14      | RSI lookback window                              |
| `rsi_yes_low`     | 50.0    | Lower RSI bound for YES entry                    |
| `rsi_yes_high`    | 70.0    | Upper RSI bound for YES entry                    |
| `rsi_no_low`      | 30.0    | Lower RSI bound for NO entry                     |
| `rsi_no_high`     | 50.0    | Upper RSI bound for NO entry                     |
| `stoch_k`         | 5       | Stochastic %K lookback window                    |
| `stoch_d`         | 3       | Stochastic %D smoothing window                   |
| `stoch_low`       | 20.0    | Lower stochastic bound                           |
| `stoch_high`      | 80.0    | Upper stochastic bound                           |
| `cross_lookback`  | 3       | Bars back to search for the EMA cross            |
| `max_price`       | 0.60    | Maximum ask price allowed for entry              |
| `max_elapsed_sec` | 300.0   | Maximum elapsed window time allowed for entry    |

## Exits
The strategy exits at the first opposite EMA cross after entry. If no opposite
cross occurs before window resolution, the position holds to resolution
(`exit_idx=None`).

## Limitations / Proxies
- Stochastic oscillator uses rolling min/max of `spot` because individual bar
  high/low data is not available in the `Market` object.
- Entry is at the best ask of the chosen side; exits at an opposite cross use
  the best bid at the exit bar.
