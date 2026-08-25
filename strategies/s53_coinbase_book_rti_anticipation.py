"""Strategy 53: Coinbase Book + RTI Anticipation.
Approximate directional book pressure from YES/NO token Level-2 orderbooks.
Large bid wall below price favors UP; large ask wall above price favors DOWN.
"""
import gzip
import json
import math
from typing import List, Optional, Tuple

import numpy as np

from engine.backtest import Signal
from engine.market import Market
from strategies.base import Strategy


def _load_orderbooks(path: str) -> Tuple[List[dict], List[dict]]:
    """Lazy-load orderbooks for the snapshots kept by Market loader."""
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            rows = json.load(f)
    except Exception:
        return [], []
    obs_up: List[dict] = []
    obs_down: List[dict] = []
    for row in rows:
        # Match Market.load_market filtering: valid timestamp + btc_price.
        t = row.get("time")
        px = row.get("btc_price")
        if t is None or px is None:
            continue
        obs_up.append(row.get("orderbook_up", {}) or {})
        obs_down.append(row.get("orderbook_down", {}) or {})
    return obs_up, obs_down


def _wall_mass(book: dict, side: str, center_price: float, band_pct: float, wall_mult: float) -> float:
    """Aggregate wall mass on one side of an orderbook.

    A "wall" is a limit-order level whose size is at least ``wall_mult`` times
    the median size among all levels inside the price band around
    ``center_price``.  Bids are scanned below center; asks are scanned above.
    """
    if side == "bid":
        levels = book.get("bids", [])
        lo = center_price * (1.0 - band_pct)
        hi = center_price
    else:
        levels = book.get("asks", [])
        lo = center_price
        hi = center_price * (1.0 + band_pct)

    sizes = []
    for lvl in levels:
        price = float(lvl.get("price", 0.0))
        if lo <= price <= hi:
            sizes.append(float(lvl.get("size", 0.0)))
    if not sizes:
        return 0.0

    median_size = float(np.median(sizes))
    if median_size <= 1e-12:
        return 0.0

    threshold = wall_mult * median_size
    return sum(s for s in sizes if s >= threshold)


def _mid_price(best_bid: float, best_ask: float) -> float:
    """Safe mid-price from top of book."""
    if not math.isnan(best_bid) and not math.isnan(best_ask) and best_bid > 0 and best_ask > best_bid:
        return 0.5 * (best_bid + best_ask)
    if not math.isnan(best_bid) and best_bid > 0:
        return best_bid
    if not math.isnan(best_ask) and best_ask > 0:
        return best_ask
    return math.nan


class S53CoinbaseBookRtiAnticipation(Strategy):
    name = "S53_Coinbase_Book_RTI_Anticipation"

    def __init__(
        self,
        band_pct: float = 0.20,
        wall_mult: float = 3.0,
        fire_threshold: float = 4.0,
        min_wall_mass: float = 0.0,
        max_price: float = 0.70,
        pull_frac: float = 0.5,
        max_hold_ticks: int = 10,
        warmup_ticks: int = 5,
    ):
        self.params = {
            "band_pct": band_pct,
            "wall_mult": wall_mult,
            "fire_threshold": fire_threshold,
            "min_wall_mass": min_wall_mass,
            "max_price": max_price,
            "pull_frac": pull_frac,
            "max_hold_ticks": max_hold_ticks,
            "warmup_ticks": warmup_ticks,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        if n < p["warmup_ticks"] + p["max_hold_ticks"] + 5:
            return []

        # Lazy-load orderbooks for this market only (keeps shared cache small).
        obs_up, obs_down = _load_orderbooks(market.path)
        if len(obs_up) != n or len(obs_down) != n:
            return []

        # Pre-compress orderbook asymmetry for the whole market.
        # A_yes positive = bid wall below YES price > ask wall above it (UP pressure).
        # A_no positive = bid wall below NO price > ask wall above it (DOWN pressure).
        # Net A = A_yes - A_no; positive favors UP, negative favors DOWN.
        A = np.zeros(n)
        for idx in range(n):
            center_up = market.price_up[idx]
            if math.isnan(center_up):
                center_up = _mid_price(market.best_bid_up[idx], market.best_ask_up[idx])
            center_down = market.price_down[idx]
            if math.isnan(center_down):
                center_down = _mid_price(market.best_bid_down[idx], market.best_ask_down[idx])

            A_yes = 0.0
            A_no = 0.0
            if not math.isnan(center_up) and center_up > 0:
                bid_wall_up = _wall_mass(
                    obs_up[idx], "bid", center_up, p["band_pct"], p["wall_mult"]
                )
                ask_wall_up = _wall_mass(
                    obs_up[idx], "ask", center_up, p["band_pct"], p["wall_mult"]
                )
                A_yes = bid_wall_up - ask_wall_up

            if not math.isnan(center_down) and center_down > 0:
                bid_wall_down = _wall_mass(
                    obs_down[idx], "bid", center_down, p["band_pct"], p["wall_mult"]
                )
                ask_wall_down = _wall_mass(
                    obs_down[idx], "ask", center_down, p["band_pct"], p["wall_mult"]
                )
                A_no = bid_wall_down - ask_wall_down

            A[idx] = A_yes - A_no

        abs_A = np.abs(A)
        warmup = p["warmup_ticks"]

        for idx in range(warmup, n - p["max_hold_ticks"] - 1):
            window = abs_A[max(0, idx - warmup):idx]
            baseline = float(np.median(window)) if len(window) else 1.0
            if baseline < 1e-12:
                baseline = 1.0

            a = float(A[idx])
            if abs(a) < p["fire_threshold"] * baseline:
                continue
            if abs(a) < p["min_wall_mass"]:
                continue

            side = "YES" if a > 0 else "NO"
            ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
            if math.isnan(ask) or ask <= 0 or ask > p["max_price"]:
                continue

            exit_idx = self._find_exit(market, idx, A, a, p)
            reason = (
                f"book_rti side={side} A={a:.1f} baseline={baseline:.1f} "
                f"ask={ask:.3f}"
            )
            return [Signal(side=side, entry_idx=idx, exit_idx=exit_idx, reason=reason)]

        return []

    def _find_exit(
        self,
        market: Market,
        entry_idx: int,
        A: np.ndarray,
        entry_A: float,
        p: dict,
    ) -> Optional[int]:
        n = len(market)
        max_j = min(n - 1, entry_idx + p["max_hold_ticks"])
        pull_level = p["pull_frac"] * abs(entry_A)

        for j in range(entry_idx + 1, max_j + 1):
            if market.rem_sec[j] < 1.0:
                return j
            # Wall pull: net asymmetry magnitude collapses below fraction of entry.
            if abs(float(A[j])) < pull_level:
                return j
            # Sign flip on the net asymmetry also counts as a pull.
            if entry_A * float(A[j]) < 0:
                return j

        return max_j

    def param_sweep(self):
        for bp in [0.10, 0.20, 0.30]:
            for wm in [2.5, 3.0, 4.0]:
                for ft in [3.0, 4.0, 5.0]:
                    for mp in [0.60, 0.70, 0.80]:
                        yield {
                            "band_pct": bp,
                            "wall_mult": wm,
                            "fire_threshold": ft,
                            "min_wall_mass": 0.0,
                            "max_price": mp,
                            "pull_frac": 0.5,
                            "max_hold_ticks": 10,
                            "warmup_ticks": 5,
                        }, f"bp{bp}_wm{wm}_ft{ft}_mp{mp}"
