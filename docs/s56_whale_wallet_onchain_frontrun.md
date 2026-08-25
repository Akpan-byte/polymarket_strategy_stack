# S56 Whale-Wallet On-Chain Front-Run

## Family
Momentum / orderbook pressure

## Idea
Large on-chain "whale" wallets often move token prices in the opening seconds of a binary window. Since raw on-chain wallet flow is unavailable in this dataset, we proxy whale activity with two early-window footprints: (1) fast token-price velocity on one side, and (2) persistent top-of-book pressure on the same side. Entering in the first two minutes while both footprints agree lets the position ride the resulting move to resolution.

## Entry rules
1. Restrict the scan to the first `early_sec` seconds of the market.
2. At each candidate tick `idx` inside the early window, compute the linear-regression slope of the token price vs `elapsed_sec` over `[0..idx]` separately for YES (`price_up`) and NO (`price_down`).
3. Select the dominant side:
   - **YES** if `velocity_up > velocity_threshold` and `velocity_up > velocity_down + dominance_margin`.
   - **NO** if `velocity_down > velocity_threshold` and `velocity_down > velocity_up + dominance_margin`.
4. Confirm orderbook pressure on the chosen side over `[0..idx]`:
   - Pressure = cumulative `(bid_chg) + (prev_ask - ask) + (token_price_chg)`, ignoring ticks with NaN quotes.
   - The chosen side's pressure must exceed `pressure_threshold` and exceed the opposite side's pressure by `dominance_margin`.
5. Entry price must be the best ask of the chosen side at `idx` and `<= max_token_price`.

## Parameters
| Parameter          | Default | Description                                            |
|--------------------|---------|--------------------------------------------------------|
| `early_sec`        | 120.0   | Length of the early front-run window in seconds        |
| `min_ticks`        | 3       | Minimum ticks required before computing velocity       |
| `velocity_threshold`| 0.0001 | Minimum token-price slope per second for a candidate   |
| `pressure_threshold`| 0.005   | Minimum cumulative pressure score on the chosen side   |
| `dominance_margin` | 0.0     | Margin by which the chosen side must dominate          |
| `max_token_price`  | 0.65    | Maximum ask price allowed for entry                    |

## Exits
The strategy holds to window resolution (`exit_idx=None`).

## Limitations / proxies
- On-chain whale wallet data is not available; token velocity + orderbook pressure are approximations.
- Only top-of-book bid/ask/quotes are present, so depth beyond level 1 is ignored.
- Sparse snapshots can make the early-window velocity estimate noisy.
