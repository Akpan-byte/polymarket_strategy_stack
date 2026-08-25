# S62 — 9-Feature Neural Ensemble Classifier

## Family
machine-learning / ensemble

## Idea
Approximate a neural ensemble classifier with three fixed-coefficient logistic
experts fed from a nine-feature vector.  Each expert specialises in a different
regime (trend, mean reversion, microstructure) and their probabilities are
combined into a single YES probability `P`.  We buy YES when `P` exceeds the
YES ask plus a margin, and buy NO when `1-P` exceeds the NO ask plus a margin.

## Entry Rules
1. Compute the feature vector at every snapshot using only data at or before
   that snapshot.
2. Compute each logistic expert output:
   - **Expert 0 — trend/momentum**: weights EMA cross, returns, YES delta, YES
     ask momentum, and NO ask momentum.
   - **Expert 1 — mean reversion**: weights RSI, Bollinger %B, and candle proxy
     with opposite signs.
   - **Expert 2 — microstructure**: weights the YES order-book imbalance proxy
     and ask momentums.
3. Ensemble `P = sum(w_i * expert_i)`.
4. Enter **YES** if `P >= best_ask_up + margin` and ask is affordable.
5. Enter **NO** if `1 - P >= best_ask_down + margin` and ask is affordable.

## Exit Rules
The position is held until the ensemble flips to the opposite side (searching
for the first index after entry where `P < 0.5` for YES or `P > 0.5` for NO).
If the flip never occurs before expiry, the position is held to resolution.

## Parameters
| Parameter        | Default   | Description                                        |
|------------------|-----------|----------------------------------------------------|
| `margin`         | 0.02      | Edge required above the ask to enter               |
| `rsi_window`     | 14        | RSI lookback window                                |
| `bb_window`      | 20        | Bollinger Band lookback window                     |
| `bb_std`         | 2.0       | Bollinger Band std-dev multiplier                  |
| `ema_fast`       | 12        | Fast EMA period                                    |
| `ema_slow`       | 26        | Slow EMA period                                    |
| `return_window`  | 10        | Ticks for return and candle proxies                |
| `pressure_window`| 10        | Ticks for ask-momentum proxies                     |
| `max_price`      | 0.70      | Maximum ask price allowed for entry                |
| `ensemble_weights`| [0.5,0.3,0.2] | Mix weights for the three experts              |

## Data Proxies / Limitations
- True volume is unavailable; volume-pressure is proxied by the YES order-book
  imbalance `(best_bid_up - best_ask_up) / (best_bid_up + best_ask_up)`.
- The classifier is intentionally simple: fixed coefficients and logistic units
  stand in for a trained neural net, which would require an offline training
  pipeline.
- The nine features are derived from `spot`, token prices, and best bid/ask
  only; deeper order-book data is not used.
- Entry uses only data at or before `entry_idx`.
