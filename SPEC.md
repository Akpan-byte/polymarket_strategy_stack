# Polymarket Strategy Stack Specification

## Data Format
- Location: `~/polybacktest_btc5m/is/` on Akpan laptop (1,143 gzipped JSON files, `{market_id}.json.gz`)
- Each file: JSON list of snapshots in chronological order.
- Snapshot fields:
  - `id`: int (optional)
  - `time`: ISO timestamp string (UTC)
  - `market_id`: str (optional)
  - `btc_price`: float (spot)
  - `price_up`: float or null
  - `price_down`: float or null
  - `orderbook_up`: {"asks": [{"size", "price"}], "bids": [...]}
  - `orderbook_down`: same
- First snapshot's `btc_price` is the strike/window-open price.
- Resolution: final snapshot's `btc_price` >= strike -> "YES" (UP) pays $1, else "NO" (DOWN) pays $1.
- Best ask/bid per snapshot from orderbook arrays (asks ascending, bids descending).

## Market Object
Precomputed `engine.market.Market` dataclass with numpy arrays:
- `market_id`, `start_ts`, `end_ts`, `strike`, `resolution`
- `ts`: epoch seconds
- `spot`, `price_up`, `price_down`
- `best_ask_up`, `best_bid_up`, `best_ask_down`, `best_bid_down`
- `rem_sec`: seconds remaining
- `elapsed_sec`: seconds since start
- `delta_pct`: (spot - strike) / strike

## Signal
`engine.backtest.Signal` dataclass:
- `side`: "YES" or "NO"
- `entry_idx`: snapshot index
- `exit_idx`: Optional[int] = None (None = hold to resolution)
- `confidence`: float = 1.0
- `reason`: str

## Strategy Interface
```python
from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy

class SXXMyStrategy(Strategy):
    name = "SXX_MyStrategy"
    def __init__(self, ...):
        self.params = {...}
    def generate_signals(self, market: Market) -> List[Signal]:
        ...
```
No look-ahead: only use data at or before `entry_idx` to decide entry.

## Sizing / Fees
Engine supports three sizing modes in `engine.sizing.DEFAULT_SIZINGS`:
- `s1_fixed_200`: $1 fixed per trade, $200 initial balance
- `s2_pctmin_200`: 0.5% of balance per trade, 5 share minimum, $200 balance
- `s3_pctmin_150`: 0.5% of balance per trade, 5 share minimum, $150 balance
Taker fee per share: `price * 0.25 * (price * (1 - price))**2`.
Entry uses best ask; intra-window exit uses best bid; resolution pays $1 or $0.

## Running
```bash
cd /config/polymarket_strategy_stack
python3 runners/run_strategy.py \
  --data /path/to/is \
  --strategy-module strategies/sXX_name.py \
  --strategy-class SXXName \
  --sizing s1_fixed_200 \
  --out-dir results
```

## Google Drive
Push `results/` and `docs/` via rclone remote `polybacktest`:
```bash
rclone sync results polybacktest:results
```

## Constraints
- No latency arbitrage (e.g., Strategy 1).
- No mispricing arbitrage / combined-cost < $1 strategies (e.g., Strategy 6, 20).
- No market making (e.g., Strategy 5, 7).
- Strategies must be viable at ~70ms execution latency (seconds-to-minutes horizons).
