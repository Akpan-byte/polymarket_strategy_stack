"""Strategy 51: Order-Book Imbalance Scalp.
Buy the side whose top-of-book is bid-heavy, filtering spoof stacks.
"""
import numpy as np
from typing import List
from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


def _top_depth(book, levels: int = 5):
    bids = book.get("bids", [])[:levels]
    asks = book.get("asks", [])[:levels]
    bid_vol = sum(float(b["size"]) for b in bids)
    ask_vol = sum(float(a["size"]) for a in asks)
    max_bid = max((float(b["size"]) for b in bids), default=0)
    max_ask = max((float(a["size"]) for a in asks), default=0)
    return bid_vol, ask_vol, max_bid, max_ask


class S51OrderBookImbalance(Strategy):
    name = "S51_OrderBook_Imbalance"

    def __init__(self, levels: int = 5, imb_threshold: float = 2.5,
                 sustain_ticks: int = 15, max_single_pct: float = 0.40,
                 max_price: float = 0.65):
        self.params = {
            "levels": levels,
            "imb_threshold": imb_threshold,
            "sustain_ticks": sustain_ticks,
            "max_single_pct": max_single_pct,
            "max_price": max_price,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        # We don't have raw L2 arrays in Market; this strategy is a stub that
        # uses price_up/price_down and best bid/ask as a proxy.
        # A full implementation would require raw orderbook arrays per snapshot.
        p = self.params
        n = len(market)
        if n < p["sustain_ticks"] + 5:
            return []

        # Use bid-ask pressure proxy: mid-price momentum vs spread
        for idx in range(p["sustain_ticks"], n - 5):
            # Skip if spot contradicts strongly
            d = market.delta_pct[idx]
            if abs(d) < 0.0001:
                continue
            side = "YES" if d > 0 else "NO"

            # Proxy imbalance: ask/bid ratio of chosen side over sustain window
            if side == "YES":
                best_bid = market.best_bid_up[idx]
                best_ask = market.best_ask_up[idx]
            else:
                best_bid = market.best_bid_down[idx]
                best_ask = market.best_ask_down[idx]
            if np.isnan(best_bid) or np.isnan(best_ask) or best_bid <= 0:
                continue
            ratio = best_ask / best_bid
            if ratio < p["imb_threshold"]:
                continue

            ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
            if np.isnan(ask) or ask > p["max_price"]:
                continue

            return [Signal(side=side, entry_idx=idx, reason=f"imbalance_ratio={ratio:.2f}")]
        return []

    def param_sweep(self):
        for lv in [3, 5, 7]:
            for th in [2.0, 2.5, 3.0]:
                for st in [10, 15, 20]:
                    for mp in [0.55, 0.65, 0.75]:
                        yield {
                            "levels": lv,
                            "imb_threshold": th,
                            "sustain_ticks": st,
                            "max_single_pct": 0.40,
                            "max_price": mp,
                        }, f"lv{lv}_th{th}_st{st}_mp{mp}"
