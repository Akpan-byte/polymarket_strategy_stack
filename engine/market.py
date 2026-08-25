"""Fast market data loader and Market dataclass."""
from __future__ import annotations
import gzip
import json
import os
from dataclasses import dataclass
from multiprocessing import cpu_count
from multiprocessing.pool import Pool
from pathlib import Path
from typing import List, Optional
import numpy as np


@dataclass(slots=True)
class Market:
    market_id: str
    start_ts: float
    end_ts: float
    strike: float
    resolution: str  # "YES" or "NO"
    ts: np.ndarray
    spot: np.ndarray
    price_up: np.ndarray
    price_down: np.ndarray
    best_ask_up: np.ndarray
    best_bid_up: np.ndarray
    best_ask_down: np.ndarray
    best_bid_down: np.ndarray
    rem_sec: np.ndarray
    elapsed_sec: np.ndarray
    delta_pct: np.ndarray
    # Source path so strategies can lazily re-read raw JSON (e.g. L2 books)
    # without bloating the shared in-memory cache.
    path: str

    def __len__(self) -> int:
        return self.ts.shape[0]


def _parse_ts(ts_val):
    if isinstance(ts_val, (int, float)):
        return float(ts_val)
    if isinstance(ts_val, str):
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
            return dt.timestamp()
        except Exception:
            return 0.0
    return 0.0


def _best_ask(book):
    asks = book.get("asks", [])
    if not asks:
        return np.nan
    # asks sorted ascending by price
    return float(asks[0]["price"])


def _best_bid(book):
    bids = book.get("bids", [])
    if not bids:
        return np.nan
    # bids sorted descending by price
    return float(bids[0]["price"])


def load_market(path: str) -> Optional[Market]:
    """Load a single market file into a Market object."""
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            rows = json.load(f)
    except Exception:
        return None
    if not rows:
        return None

    # Filter rows with valid timestamp and spot price
    valid = []
    for row in rows:
        t = _parse_ts(row.get("time"))
        px = row.get("btc_price")
        if t > 0 and px is not None:
            valid.append(row)
    if not valid:
        return None

    n = len(valid)
    ts = np.empty(n, dtype=np.float64)
    spot = np.empty(n, dtype=np.float64)
    price_up = np.full(n, np.nan, dtype=np.float64)
    price_down = np.full(n, np.nan, dtype=np.float64)
    best_ask_up = np.full(n, np.nan, dtype=np.float64)
    best_bid_up = np.full(n, np.nan, dtype=np.float64)
    best_ask_down = np.full(n, np.nan, dtype=np.float64)
    best_bid_down = np.full(n, np.nan, dtype=np.float64)

    for i, row in enumerate(valid):
        ts[i] = _parse_ts(row.get("time"))
        spot[i] = float(row.get("btc_price", 0))
        pu = row.get("price_up")
        pd = row.get("price_down")
        if pu is not None:
            price_up[i] = float(pu)
        if pd is not None:
            price_down[i] = float(pd)
        ob_up = row.get("orderbook_up", {}) or {}
        ob_down = row.get("orderbook_down", {}) or {}
        best_ask_up[i] = _best_ask(ob_up)
        best_bid_up[i] = _best_bid(ob_up)
        best_ask_down[i] = _best_ask(ob_down)
        best_bid_down[i] = _best_bid(ob_down)

    market_id = str(rows[0].get("market_id", Path(path).stem))
    start_ts = ts[0]
    end_ts = ts[-1]
    strike = spot[0]
    resolution = "YES" if spot[-1] >= strike else "NO"

    rem_sec = end_ts - ts
    elapsed_sec = ts - start_ts
    delta_pct = (spot - strike) / strike

    return Market(
        market_id=market_id,
        start_ts=start_ts,
        end_ts=end_ts,
        strike=strike,
        resolution=resolution,
        ts=ts,
        spot=spot,
        price_up=price_up,
        price_down=price_down,
        best_ask_up=best_ask_up,
        best_bid_up=best_bid_up,
        best_ask_down=best_ask_down,
        best_bid_down=best_bid_down,
        rem_sec=rem_sec,
        elapsed_sec=elapsed_sec,
        delta_pct=delta_pct,
        path=str(path),
    )


def load_markets(data_dir: str, max_files: Optional[int] = None,
                 workers: Optional[int] = None) -> List[Market]:
    """Load all .json.gz market files in data_dir in parallel."""
    path = Path(data_dir)
    files = sorted(path.glob("*.json.gz"))
    if max_files:
        files = files[:max_files]
    if workers is None:
        workers = max(1, min(cpu_count(), 16))
    markets: List[Market] = []
    if len(files) < 50 or workers == 1:
        for fp in files:
            m = load_market(str(fp))
            if m is not None:
                markets.append(m)
        return markets
    with Pool(workers) as pool:
        results = pool.imap_unordered(load_market, [str(fp) for fp in files], chunksize=20)
        for m in results:
            if m is not None:
                markets.append(m)
    return markets


def cache_markets(markets: List[Market], cache_path: str):
    """Cache loaded markets to disk for fast reloads."""
    import pickle
    os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
    with open(cache_path, "wb") as f:
        pickle.dump(markets, f, protocol=pickle.HIGHEST_PROTOCOL)


def load_cached_markets(cache_path: str) -> List[Market]:
    import pickle
    with open(cache_path, "rb") as f:
        return pickle.load(f)
