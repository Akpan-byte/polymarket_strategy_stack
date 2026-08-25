# S64 Markov-Regime-Switched Signal Routing

## Family
Regime-switching / hybrid

## Idea
BTC's 5-minute binary window alternates between trending, ranging and neutral
phases.  Classify the current phase from a 10-minute spot return, volatility
percentile and Bollinger-bandwidth percentile, then route the signal to the
engine best suited for that phase: momentum for trends, mean-reversion for
ranges, and a late-window drift entry for neutral periods.

## Entry rules
1. **Regime inputs** (computed at each sample using only data at or before the
   sample):
   - `ret10`: spot return over the trailing `return_lookback_sec` (default 10
     minutes).
   - `vol_pct`: percentile of the rolling standard deviation of spot returns
     within a trailing window.
   - `bw_pct`: percentile of Bollinger bandwidth `(upper - lower) / mean` within
     a trailing window.
2. **Raw classification**:
   - `TREND`: `abs(ret10) >= trend_return_threshold` **and** high volatility
     (`vol_pct >= vol_percentile_threshold`).
   - `RANGE`: high bandwidth (`bw_pct >= bandwidth_percentile_threshold`) or
     elevated volatility without a directional trend.
   - `NEUTRAL`: everything else.
3. **Hysteresis**: the raw label must persist for `hysteresis` consecutive
   samples before the active regime switches.
4. **Engine routing**:
   - `TREND` → momentum entry in the direction of `ret10`.
   - `RANGE` → Bollinger-band reversion (YES near lower band, NO near upper
     band).
   - `NEUTRAL` → late-window drift entry when `rem_sec <= late_window_sec`,
     taking the side of the current spot-vs-strike delta.
5. Entry price is the best ask of the chosen side and must be `<= max_price`.

## Parameters
| Parameter                        | Default | Description                                              |
|----------------------------------|---------|----------------------------------------------------------|
| `return_lookback_sec`            | 600.0   | Seconds used for the 10-minute return input              |
| `trend_return_threshold`         | 0.001   | Absolute return threshold for TREND classification       |
| `vol_window`                     | 5       | Rolling window for spot-return volatility                |
| `vol_percentile_threshold`       | 70.0    | Volatility percentile required for TREND / RANGE         |
| `bb_window`                      | 5       | Bollinger Band rolling window                            |
| `bb_std`                         | 2.0     | Bollinger Band standard-deviation multiplier             |
| `bandwidth_percentile_threshold` | 70.0    | Bandwidth percentile required for RANGE classification   |
| `hysteresis`                     | 3       | Consecutive samples required before switching regime     |
| `max_price`                      | 0.70    | Maximum ask price allowed for entry                      |
| `late_window_sec`                | 30.0    | Remaining seconds for NEUTRAL late-window entry          |

## Exits
The strategy holds to window resolution (`exit_idx=None`).

## Limitations / proxies
- Regime inputs are approximated from spot only; token-specific order-flow is
  not used.
- Volatility and bandwidth percentiles are computed from the current market's
  history, so classification quality depends on having enough samples.
- The "Markov" framing is conceptual: transitions are driven by hysteresis, not
  an estimated transition matrix.
- Default rolling windows are intentionally small so the strategy can run on
  sparse caches; the 10-minute return falls back to the earliest available
  sample when history is shorter than 10 minutes.
