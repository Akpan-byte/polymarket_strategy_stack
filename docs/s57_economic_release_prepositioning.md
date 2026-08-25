# S57 — Economic-Release Pre-Positioning

## Family
Event-driven / macro pre-positioning

## Idea
Major macro-economic releases tend to move the underlying asset around fixed
UTC hours. This strategy synthetically schedules those release times and
pre-positions in the binary market when the entry token is still cheap.

## Entry rules
1. Build a synthetic calendar of macro-release events at UTC hours
   `event_hours` (default 12, 13, 18, 19).
2. For each event that falls inside the market's time window:
   - Compute spot velocity over the last `velocity_window` ticks.
   - If velocity is positive, expect an upward deviation and enter **YES**;
     if negative, enter **NO**.
   - Require `abs(velocity) >= min_velocity` to avoid flat-market noise.
3. Entry must occur before the event and no earlier than
   `max_pre_event_sec` seconds before it.
4. The chosen side's best ask must be available and `<= max_token_price`.

## Parameters
| Parameter           | Default | Description                                          |
|---------------------|---------|------------------------------------------------------|
| `event_hours`       | [12,13,18,19] | UTC hours treated as synthetic release times   |
| `post_exit_sec`     | 300.0   | Seconds after the event to exit                      |
| `velocity_window`   | 5       | Bars used to compute pre-event spot velocity         |
| `min_velocity`      | 0.0     | Minimum absolute velocity (fraction) required        |
| `max_token_price`   | 0.55    | Maximum ask price allowed for entry                  |
| `max_pre_event_sec` | 1800.0  | Latest pre-event entry window (seconds before event) |

## Exits
The strategy exits at `event_time + post_exit_sec`. If that timestamp is past
the end of the market window, the position is held to resolution.

## Limitations / proxies
- Events are synthetic fixed-UTC-hour events, not real macro-release timestamps.
- "Expected deviation" is proxied by recent spot velocity, not an actual
  economic surprise forecast.
- The strategy does not model release calendars, holidays, or delayed releases.
