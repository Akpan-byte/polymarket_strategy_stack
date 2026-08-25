# S53 — Coinbase Book + RTI Anticipation

## Family
microstructure

## Idea
Directional pressure in Polymarket's YES/NO token orderbooks anticipates
short-term spot movement.  A large bid wall below the current YES price
suggests latent buying demand (UP); a large ask wall above the YES price
suggests supply overhead (DOWN).  The same logic is inverted for the NO
token.  The strategy combines the two books into a single net asymmetry
score and enters when that score is extreme relative to its recent history.

## Entry Rules
1. For each snapshot, aggregate "walls" on each token book:
   - A wall is a limit level whose size is at least `wall_mult` times the
     median size among all levels inside the price band `band_pct` around
     the token price.
   - YES token asymmetry: `A_yes = bid_wall_below − ask_wall_above`.
   - NO token asymmetry: `A_no = bid_wall_below − ask_wall_above`.
2. Net asymmetry: `A = A_yes − A_no`.
   - Positive `A` favors UP; negative `A` favors DOWN.
3. Fire only when `|A| >= fire_threshold * median(|A| over history so far)`
   and `|A| >= min_wall_mass`.
4. Entry ask of the chosen side must be available and `<= max_price`.

## Exit Rules
The first condition that fires sets `exit_idx`:
1. **Wall pull**: net asymmetry magnitude drops below `pull_frac` of the
   entry magnitude or the sign flips.
2. **Expiry safety**: fewer than 1 second remains.
3. **Hard time stop**: `max_hold_ticks` elapsed.

## Parameters
| Parameter        | Default | Description                                                |
|------------------|---------|------------------------------------------------------------|
| `band_pct`       | 0.20    | Price band around token price for wall aggregation         |
| `wall_mult`      | 3.0     | Size multiplier defining a wall vs. median band size       |
| `fire_threshold` | 4.0     | `|A|` must exceed this × running median `|A|`               |
| `min_wall_mass`  | 0.0     | Minimum absolute `|A|` required to fire                    |
| `max_price`      | 0.70    | Maximum entry ask allowed                                  |
| `pull_frac`      | 0.5     | Exit when `|A|` falls to this fraction of entry `|A|`      |
| `max_hold_ticks` | 10      | Longest allowed open duration in snapshots                 |
| `warmup_ticks`   | 5       | Ticks used to build the running median baseline            |

## Limitations / Proxies
- Full Level-2 event streams (adds/cancels/trades) are not available; the
  strategy works from snapshot orderbooks stored in `Market.orderbook_up`
  and `Market.orderbook_down`.
- "Coinbase Book" in the description refers to the style of book-pressure
  signal; the actual data source is the Polymarket CLOB snapshots provided
  in the backtest bundle.
- Wall aggregation uses token price (or best-bid/ask mid when price is
  missing) as the band center; real-time mark or mid may differ slightly.
