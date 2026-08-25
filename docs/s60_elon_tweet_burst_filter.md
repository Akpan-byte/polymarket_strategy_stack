# S60 Elon/Key-Figure Tweet-Burst Filter

## Family
Momentum / event proxy

## Idea
A sudden spot move acts as a synthetic "tweet burst" from a key figure. If the
token has not fully repriced to the move, enter momentum in the burst direction
and hold to resolution.

## Entry rules
1. Compute the spot return over `burst_window` observations.
2. Trigger only if `|spot_return| >= min_delta`.
3. Map current spot delta to a synthetic fair YES probability via a logistic
   curve: `fair_yes = sigmoid(delta_pct * fair_slope)`.
4. Compute the expected neutral-to-fair move (`fair_yes - neutral_price`) and
   the actual token move from neutral.
5. Enter the momentum side (YES for up-burst, NO for down-burst) only if the
   token has repriced by less than `max_repriced_frac` of the expected move.
6. Entry price must be the best ask of the chosen side and `<= max_price`.

## Parameters
| Parameter           | Default | Description                                           |
|---------------------|---------|-------------------------------------------------------|
| `burst_window`      | 5       | Rolling window for spot-burst measurement             |
| `min_delta`         | 0.0005  | Minimum absolute spot return (5 bps) to trigger       |
| `max_repriced_frac` | 0.5     | Max fraction of expected move already priced in       |
| `fair_slope`        | 500.0   | Logistic slope mapping `delta_pct` to fair probability|
| `neutral_price`     | 0.5     | Neutral probability baseline                          |
| `max_price`         | 0.70    | Maximum ask price allowed for entry                   |

## Exits
The strategy holds to window resolution (`exit_idx=None`).

## Limitations / proxies
- No real tweet data; the burst is inferred from spot price action only.
- The fair-probability mapping is a heuristic logistic proxy, not an empirical
  delta-to-probability model.
- Order-book depth beyond best bid/ask is not available.
