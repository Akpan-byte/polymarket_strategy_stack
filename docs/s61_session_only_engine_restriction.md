# S61 Session-Only Engine Restriction

## Family
Session / time-of-day filter

## Idea
The S21 Window-Delta Purist signal is profitable only during certain UTC
hours. This strategy gates every S21 candidate by a precomputed hour-map of
historical expectancy, staying flat when the session has poor or
insufficiently-sampled edge.

## Entry rules
1. Compute the S21 Window-Delta Purist candidate signal.
2. Read the UTC hour of the candidate entry timestamp.
3. Look up `(expectancy, sample_count)` for that hour in `hour_map`.
4. Allow the signal only if:
   - `sample_count >= min_samples`
   - `expectancy >= min_expectancy`
5. Otherwise remain flat.

## Parameters
| Parameter         | Default | Description                                        |
|-------------------|---------|----------------------------------------------------|
| `t_entry`         | 10.0    | Target seconds before close for S21 entry          |
| `delta_full`      | 0.001   | S21 full-size delta threshold                      |
| `delta_half`      | 0.0002  | S21 half-size delta threshold                      |
| `delta_min`       | 0.00005 | S21 minimum delta magnitude                        |
| `use_oracle_veto` | False   | S21 oracle-veto flag (currently a no-op)           |
| `min_expectancy`  | 0.52    | Minimum hour-level win-rate expectancy to trade    |
| `min_samples`     | 30      | Minimum observations behind an hour's expectancy   |
| `hour_map`        | flat    | Dict `hour -> (expectancy, sample_count)`          |

## Exits
Same as S21: hold to window resolution (`exit_idx=None`).

## Limitations / proxies
- The default `hour_map` is a flat, permissive placeholder. Real edge requires
  training the map on historical data.
- Expectancy is approximated by win rate; it ignores payout size and fees.
- No online update of the hour map during the backtest.
