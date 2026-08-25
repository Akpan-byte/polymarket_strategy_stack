# S65 Adaptive Self-Tuner

## Family
Late-window delta / meta-strategy

## Idea
Take the same late-window delta entry as S21, but adjust the entry threshold
based on a rolling win-rate score.  When recent simulated performance is
strong relative to an expected baseline, the strategy loosens its threshold
and trades more aggressively; when performance is weak it tightens, and when
it is very weak it suspends entries entirely.

## Entry rules
1. Locate the snapshot closest to `T - t_entry` seconds before expiry, requiring
   the remaining time to be between 3 and 30 seconds.
2. Compute the adaptive factor from the rolling win rate of prior simulated
   trades over `wr_window` outcomes versus `expected_wr`:
   - `WR - expected_wr >= +loosen_pts` → multiply `delta_min` by `loosen_mult`
     (lower threshold, easier entry).
   - `WR - expected_wr <= -suspend_pts` → suspend entries for this market.
   - `WR - expected_wr <= -tighten_pts` → multiply `delta_min` by
     `tighten_mult` (higher threshold, harder entry).
   - Otherwise → use `delta_min` unchanged.
3. If `abs(delta_pct[idx]) >= adapted threshold`, enter in the direction of the
   delta: **YES** for positive delta, **NO** for negative delta.
4. Entry ask must be available and `<= max_price`.

## Parameters
| Parameter      | Default | Description                                              |
|----------------|---------|----------------------------------------------------------|
| `t_entry`      | 10.0    | Target seconds before expiry for entry                   |
| `delta_min`    | 0.0002  | Base minimum absolute delta required to enter            |
| `max_price`    | 0.70    | Maximum ask price allowed for entry                      |
| `wr_window`    | 20      | Rolling window of simulated outcomes for win-rate score  |
| `expected_wr`  | 0.50    | Baseline win rate to compare against                     |
| `loosen_pts`   | 0.05    | Win-rate excess that triggers a looser threshold         |
| `tighten_pts`  | 0.05    | Win-rate deficit that triggers a tighter threshold       |
| `suspend_pts`  | 0.10    | Win-rate deficit that suspends entries                   |
| `loosen_mult`  | 0.75    | Multiplier applied to `delta_min` when loosening         |
| `tighten_mult` | 1.5     | Multiplier applied to `delta_min` when tightening        |

## Exits
The strategy holds to window resolution (`exit_idx=None`).

## Limitations / proxies
- The win-rate tracker is stateful across markets.  Outcomes are determined by
  the market resolution, which is only known after expiry; the current signal
  does not use its own outcome, only prior history.
- Adaptation speed depends on how many prior markets generated signals.
- No explicit stop-loss or take-profit beyond holding to resolution.
