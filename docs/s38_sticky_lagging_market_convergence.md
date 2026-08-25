# S38 Sticky Lagging-Market Convergence

## Family
Momentum / convergence

## Idea
When BTC has moved decisively in one direction (the "leader"), correlated
markets sometimes lag. Buy the lagging side once the underlying spot trend
confirms direction and hold while the binary price converges toward the leader.

This implementation is a single-market proxy: the current market is treated as
the laggard and its spot move is used as the leader signal.

## Entry rules
1. Compute the spot trend over `trend_window` bars.
2. **Leader condition**: `delta_pct[idx]` must exceed `leader_delta` in the
trend direction (positive for YES, negative for NO).
3. **Laggard condition**: the best ask of the chosen side must be between
`min_price` and `laggard_max` and must be below `leader_implied - target_offset`
to leave convergence headroom.
4. Return one signal per market; no look-ahead beyond `entry_idx`.

## Parameters
| Parameter      | Default | Description                                      |
|----------------|---------|--------------------------------------------------|
| `leader_delta` | 0.002   | Spot delta threshold that triggers the leader side |
| `laggard_max`  | 0.80    | Maximum ask price allowed for a laggard entry    |
| `trend_window` | 5       | Bars used to confirm spot direction              |
| `leader_implied`| 0.95   | Implied leader price used to compute exit target |
| `target_offset`| 0.02    | Exit target = `leader_implied - target_offset`   |
| `min_price`    | 0.02    | Minimum ask price to avoid illiquid extremes     |

## Exits
The signal holds to window resolution (`exit_idx=None`). In a live
multi-market implementation, the position would also be exited when the
laggard reaches `leader_implied - 0.02` or at T-15s, whichever comes first.
The backtest proxy avoids using future price data to set `exit_idx`.

## Limitations / proxies
- True cross-market convergence requires data for multiple correlated markets
  (BTC, ETH, SOL, XRP). This local version uses the current market's spot move
  as the leader proxy.
- The target-price and T-15s exits are not executed in the backtest to prevent
  look-ahead; only the resolution exit is modeled.
