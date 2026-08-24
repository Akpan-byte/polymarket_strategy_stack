# S69 — Complementary-Exit Discipline

## Family
microstructure-exits

## Source
Benjam1nCup "Lost token sniper" exit-side logic (the combined-price arbitrage
mechanics are excluded).

## Concept
When a directional position's thesis weakens, sell the soon-to-be-losing token
while it still has residual value rather than riding it to zero.  A simple
model probability of winning is recomputed each snapshot; when it decays below
half of the entry probability and the token bid is still above the residual
floor, the position is exited.

## Entry Rules
1. Spot delta at `idx` is at least `min_delta` and determines the side
(`YES` if positive, `NO` if negative).
2. Short-term token trend over `trend_window` ticks agrees with delta.
3. Entry ask is available and `<= max_price`.

## Exit Rules
The first condition that fires sets `exit_idx`:
1. **Model decay**: `_model_prob(j, side) < decay_factor * _model_prob(entry_idx, side)`.
   Only triggers if the token bid is still >= `residual_floor`.
2. **Expiry safety**: fewer than 1 second remains.
3. **Hard time stop**: `max_hold_ticks` elapsed.

If the token bid drops below `residual_floor`, the strategy does not sell there
and instead holds the lottery ticket to resolution.

## Model Probability Proxy
The winning probability is approximated with a short-horizon Black-Scholes-style
binary pricer:
- Compute realized volatility from recent spot returns.
- Map spot delta and time remaining to a normal CDF probability.
- For a NO position, use `1 - P(UP)`.

## Parameters
- `trend_window` (int): lookback ticks for entry trend confirmation.
- `min_delta` (float): minimum absolute spot delta.
- `max_price` (float): maximum entry ask allowed.
- `decay_factor` (float): model probability must fall below this fraction of
the entry probability to trigger exit.
- `residual_floor` (float): do not sell below this bid (hold to resolution).
- `max_hold_ticks` (int): longest allowed open duration.

## Data Proxies / Limitations
- The fair-value model is a volatility-adjusted normal-CDF proxy; it is not a
trained neural model.
- Cross-market calibration of the `decay_factor` threshold is not performed;
the default 0.5 follows the source blueprint.
- Entry uses only data at or before `entry_idx`.
