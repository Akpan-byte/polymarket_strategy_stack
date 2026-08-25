# S63 LLM-Filtered Composite with Mechanical Trend Veto

## Family
Directional / trend-filtered momentum

## Idea
Replace the LLM filter from the original concept with a cheap mechanical
trend veto. The strategy takes a directional position in line with recent
spot deviation and short-term momentum, but only if a 10-minute trend does
not strongly oppose the trade.

## Entry rules
1. Locate the snapshot closest to `T - t_entry` seconds remaining.
2. Require `abs(delta_pct) >= delta_min`, where `delta_pct` is the spot
   deviation from the market open strike.
3. Compute short-term momentum as the change in `delta_pct` over the last
   `momentum_window_sec`.
4. Form a composite score: `score = delta_pct + momentum_weight * momentum`.
   The trade side is **YES** if `score > 0`, otherwise **NO**.
5. Compute a 10-minute trend as the percentage change in `spot` over
   `trend_window_sec`.
6. **Veto**: if `abs(trend) >= trend_threshold` and the trend sign opposes
   the score sign, skip the trade. Otherwise, allow the trade.
7. Enter at the best ask of the chosen side if it is valid (non-NaN and
   strictly between 0 and 1).

## Parameters
| Parameter           | Default | Description                                       |
|---------------------|---------|---------------------------------------------------|
| `t_entry`           | 30.0    | Target seconds before window close for entry      |
| `momentum_window_sec`| 60.0   | Look-back window for short-term momentum          |
| `trend_window_sec`  | 600.0   | 10-minute trend look-back window                  |
| `delta_min`         | 0.0001  | Minimum `abs(delta_pct)` required to trade        |
| `momentum_weight`   | 1.0     | Weight applied to momentum in the score           |
| `trend_threshold`   | 0.0002  | Minimum `abs(trend)` that triggers a veto         |

## Exits
The strategy holds to window resolution (`exit_idx=None`).

## Limitations / proxies
- The LLM component is replaced entirely by a mechanical trend filter.
- Trend and momentum are computed from `spot` only; token order-book depth
  beyond the best ask is ignored.
- If the 10-minute look-back exceeds available market history the trend is
  treated as zero (i.e., the trade is allowed).
