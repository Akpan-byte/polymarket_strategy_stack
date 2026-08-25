# S68 Price Field Staged Exits

## Family
Parametric value / momentum

## Idea
A logistic price field estimates fair contract value from two observable
quantities: seconds remaining in the window and the absolute spot delta.  When
the best ask trades at a fixed discount to that field, the strategy enters
directionally and splits the position into equal legs to approximate staged
exits in a backtest that only supports market exits at resolution.

## Entry rules
1. At each bar `idx`, compute the price field
   `field = L / (1 + exp(-z))` where
   `z = bias + k_t * (rem_sec / 60) + k_d * |delta_pct| * 10,000`.
2. Require `min_rem_sec <= rem_sec <= max_rem_sec` and `|delta_pct| >= min_delta`.
3. Set `side = "YES"` if `delta_pct >= 0`, otherwise `"NO"`.
4. Let `ask = best_ask_up` for YES and `best_ask_down` for NO.
5. Enter if `ask <= field - entry_margin`, `ask > 0`, and `ask <= max_ask`.

## Parameters
| Parameter      | Default | Description                                          |
|----------------|---------|------------------------------------------------------|
| `L`            | 0.85    | Maximum field level (logistic ceiling)               |
| `bias`         | 0.10    | Logistic intercept                                   |
| `k_t`          | -0.04   | Time coefficient (more time → lower field)           |
| `k_d`          | 0.06    | Delta coefficient (larger delta → higher field)      |
| `entry_margin` | 0.05    | Required discount of field over ask                  |
| `min_delta`    | 0.0002  | Minimum absolute spot delta to consider              |
| `max_ask`      | 0.75    | Maximum ask price allowed for entry                  |
| `min_rem_sec`  | 30.0    | Earliest allowed entry (seconds before close)        |
| `max_rem_sec`  | 240.0   | Latest allowed entry (seconds before close)          |
| `n_legs`       | 3       | Number of equal staged-exit legs emitted per entry   |

## Exits
Each emitted leg sets `exit_idx=None` and is held to window resolution.  This
respects the no-look-ahead constraint; live staged take-profits at +4¢,
+8¢/field, and resolution are not simulated by the current backtest engine.

## Limitations / proxies
- The logistic field is an ad-hoc parametric model, not an estimate of true win
  probability.
- Staged exits are approximated by multiple resolution-held legs; true limit
  orders and partial fills are not modeled.
- Entry uses the first qualifying bar only; no re-entry logic is implemented.
