# S70 Four-Channel Confluence

## Family
Multi-signal ensemble

## Idea
Combine four orthogonal market-read channels into a single composite score
and enter when the ensemble reaches a strong directional consensus.  Each
channel votes between -1 and +1, and the position follows the sign of the
weighted mean.

## Channels
1. **Sentiment** — spot-vs-strike delta (`delta_pct`).  Positive delta
   votes YES, negative votes NO.
2. **Liquidity** — top-of-book spread tightness.  A tight spread in the
   direction of the prevailing delta adds conviction; a wide spread
   attenuates the vote.
3. **Supply-demand pressure** — migration of the orderbook mid price.
   Rising mid on the UP token or falling mid on the DOWN token votes with
   the prevailing delta.
4. **Volatility-adjusted momentum** — spot return over `window` bars
   normalized by realized volatility over the same window.

## Entry rules
1. Compute the four channel votes at every bar using only data at or before
   the bar.
2. `composite = weighted_mean(votes)`.
3. Enter **YES** if `composite >= entry_threshold`; enter **NO** if
   `composite <= -entry_threshold`.
4. Entry price must be the best ask of the chosen side and `<= max_price`.

## Parameters
| Parameter       | Default | Description                                           |
|-----------------|---------|-------------------------------------------------------|
| `window`        | 10      | Bars used for momentum/volatility lookback            |
| `delta_scale`   | 0.001   | Scale for clipping sentiment vote to [-1, 1]          |
| `spread_max`    | 0.05    | Max relative spread used for liquidity vote             |
| `pressure_scale`| 0.01    | Mid-change scale for clipping pressure vote            |
| `weights`       | dict    | Per-channel weights (sentiment/liquidity/pressure/momentum) |
| `entry_threshold`| 0.40   | Minimum absolute composite required for entry          |
| `max_price`     | 0.70    | Maximum ask price allowed for entry                   |

## Exits
The strategy holds to window resolution (`exit_idx=None`).

## Limitations / proxies
- Orderbook depth beyond best bid/ask is not available, so liquidity and
  pressure are proxied from top-of-book quotes only.
- Derivatives channel uses spot momentum as a proxy because token-orderbook
  history is not deep enough for a true volatility surface.
- Weight choices are ad-hoc; a proper optimization sweep is recommended.
