# S59 Binance Boundary Stop-Hunt Fade

## Family
Mean reversion

## Idea
In the final two minutes of a 5-minute BTC binary window, a fast spot spike that
triggers boundary stops often stalls while the token overreacts. This strategy
fades the spike once the move is large relative to the recent baseline and the
chosen token side has cheapened by at least a few cents.

## Entry rules
1. Time window: only consider snapshots with `rem_sec <= 120` and at least
   `3s` left.
2. Compute the 30-second spot move ending at the current snapshot.
3. Require `abs(move_30s) >= spike_pct`.
4. Compare the move to the average absolute 30-second move over the prior
   `avg_lookback_sec`. Enter only if the spike is at least `spike_ratio` times
   that baseline.
5. **Fade the spike**: if spot moved up, enter **NO**; if down, enter **YES**.
6. Token overreaction: the price of the chosen token side must have moved at
   least `token_react` over the same 30-second window.
7. Skip if the spot has been moving in the same direction continuously for more
   than `max_divergence_sec`.
8. Entry price must be the best ask of the chosen side and `<= max_price`.

## Parameters
| Parameter           | Default | Description                                       |
|---------------------|---------|---------------------------------------------------|
| `spike_pct`         | 0.0010  | Minimum 30s spot move (0.10%)                     |
| `avg_lookback_sec`  | 90.0    | Window for the baseline average move              |
| `spike_ratio`       | 2.5     | Spike must exceed baseline by at least this ratio |
| `token_react`       | 0.08    | Minimum token-price move (cents) confirming fade  |
| `max_price`         | 0.75    | Maximum ask price allowed for entry               |
| `max_divergence_sec`| 60.0    | Skip if same-direction drift persists this long   |

## Exits
The strategy holds to window resolution (`exit_idx=None`).

## Limitations / proxies
- The 30s "spot move" is measured between the current snapshot and the nearest
  snapshot about 30 seconds earlier; snapshot spacing is irregular.
- "Average move much smaller" is proxied by a rolling mean of absolute 30s
  moves.
- "Token overreacted" is proxied by the chosen side's token price change over
  the same 30s window.
- The divergence-persistence filter is a simple same-direction spot-move check.
