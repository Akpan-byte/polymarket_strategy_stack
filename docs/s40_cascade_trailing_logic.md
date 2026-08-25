# S40 Cascade Trailing Logic

## Family
Directional scaling / stop discipline

## Idea
Instead of entering a BTC 5-minute binary position all at once, scale in across
four tranches as the thesis confirms. Each tranche carries its own stop, so a
wrong move exits only the capital already deployed while a strong move builds
size into conviction.

## Entry rules
1. **Probe (25%)**: enter the first tranche when time remaining is at most
   `t_probe` seconds and the absolute spot delta (`|delta_pct|`) is at least
   `entry_delta`. Side is YES for positive delta, NO for negative delta.
2. **Widen add (25%)**: add when the absolute delta has widened by at least
   `widen_ratio` (e.g. 50%) from the probe delta and still agrees with the
   original side.
3. **T-60 add (25%)**: at the snapshot closest to `t_add_60` seconds remaining,
   add if the chosen-side token ask is still at least `fair_discount_cents`
   below fair (`fair=0.5`) and the delta still agrees with the side.
4. **T-15 add (25%)**: at the snapshot closest to `t_add_15` seconds remaining,
   add a final tranche if the delta still agrees with the side.
5. Entry price must be the best ask of the chosen side and `<= max_price`.
6. If any earlier tranche's stop is hit before a later tranche entry, the
   remaining cascade is cancelled.

## Parameters
| Parameter            | Default | Description                                          |
|----------------------|---------|------------------------------------------------------|
| `entry_delta`        | 0.001   | Minimum `|delta_pct|` for the probe entry            |
| `t_probe`            | 150.0   | Latest remaining-seconds allowed for the probe       |
| `widen_ratio`        | 0.5     | Required delta widening factor from probe delta      |
| `t_add_60`           | 60.0    | Target remaining seconds for the T-60 add            |
| `t_add_15`           | 15.0    | Target remaining seconds for the final add           |
| `stop_cents`         | 0.08    | Stop distance in dollars from each tranche's entry   |
| `fair_discount_cents`| 0.04    | Token must be at least this far below 0.5 for T-60   |
| `max_price`          | 0.70    | Maximum ask price allowed for any entry              |

## Exits
Each tranche exits at the first snapshot after its entry where the chosen-side
best bid is at or below its entry ask minus `stop_cents`. If the stop is never
hit, the tranche holds to window resolution (`exit_idx=None`).

## Limitations / proxies
- The cascade is modelled as up to four independent `Signal` trades per market;
  the backtest engine does not share state between them, so the cancellation
  rule is enforced by checking whether earlier stops would have triggered
  before a later entry.
- Ratcheting stops are approximated by a fixed -8c stop per tranche; dynamic
  stop raising as the trade moves favorably is not implemented.
- Order-book depth beyond best bid/ask is not available.
