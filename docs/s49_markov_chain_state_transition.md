# S49 Markov-Chain State-Transition Prediction

## Family
Probabilistic / discrete-state prediction

## Idea
BTC's 5-minute binary delta can be coarsely discretized into a small number of
states. By learning a first-order transition matrix over a rolling history, the
strategy predicts the most likely next state. When the predicted probability of
a directional state is high enough to cover the ask, spread, and taker fee with
at least a 4-cent edge, it enters at the next window open.

## Entry rules
1. Map `delta_pct` into `n_states` fixed symmetric buckets over a ±1% delta
   span (extremes clip into the outer buckets).
2. For each window close `i`, read the current state from `delta_pct[i]`.
3. Estimate `P(next_state | current_state)` from the most recent
   `history_window` observations.
4. Select the next state with maximum probability.
5. **Long**: if `next_state > current_state` and `max_prob - ask - fee >= edge_threshold`,
   enter **YES** at index `i+1`.
6. **Short**: if `next_state < current_state` and `max_prob - ask - fee >= edge_threshold`,
   enter **NO** at index `i+1`.
7. Entry price must be the best ask of the chosen side and `<= max_price`.

## Parameters
| Parameter                | Default | Description                                           |
|--------------------------|---------|-------------------------------------------------------|
| `n_states`               | 3       | Number of discrete delta states                       |
| `history_window`         | 15      | Observations used to estimate transitions             |
| `min_history`            | 10      | Minimum index before any signal is generated          |
| `prob_threshold`         | 0.55    | Minimum predicted probability to consider an entry    |
| `edge_threshold`         | 0.04    | Required net edge (predicted prob - ask - fee)        |
| `max_price`              | 0.70    | Maximum ask price allowed for entry                   |
| `rolling_history_cap`    | 200     | Maximum predictions/outcomes retained for kill switch |
| `kill_switch_divergence` | 0.08    | Disable signals if live WR diverges > 8 pp from expected |

## Exits
The strategy holds to window resolution (`exit_idx=None`).

## Limitations / proxies
- First-order Markov assumption ignores higher-order dependencies and market
  microstructure.
- Fixed ±1% bin edges are used to avoid look-ahead; markets with very small
  or very large deltas will pile into the outer/inner buckets.
- The kill switch evaluates one market late because trade outcomes are not fed
  back into `generate_signals` directly.
- Taker fee multiplier is approximated at 0.25 (the default sizing multiplier);
  actual fees depend on the sizing config used in the runner.
