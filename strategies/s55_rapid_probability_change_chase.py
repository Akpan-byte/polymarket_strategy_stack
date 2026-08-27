"""Strategy 55: Rapid Probability-Change Chase (Early Leg Only).
Chase a fast token move (>= 4c in ~10s) only while price is still within 6c of
the move's origin.  Uses a hard invalidation on any counter-tick >= 2c and a
profit target in the 5-8c range.  No new chase inside the final 60s.
"""
import numpy as np
from typing import List, Optional

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S55RapidProbabilityChangeChase(Strategy):
    name = "S55_RapidProbability_ChangeChase"

    def __init__(
        self,
        chase_window: int = 10,
        alert_thresh: float = 0.04,
        origin_slop: float = 0.06,
        counter_tick_exit: float = 0.02,
        take_profit: float = 0.065,
        min_delta: float = 0.0001,
        max_price: float = 0.75,
        max_hold_ticks: int = 60,
    ):
        self.params = {
            "chase_window": chase_window,
            "alert_thresh": alert_thresh,
            "origin_slop": origin_slop,
            "counter_tick_exit": counter_tick_exit,
            "take_profit": take_profit,
            "min_delta": min_delta,
            "max_price": max_price,
            "max_hold_ticks": max_hold_ticks,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        w = p["chase_window"]
        if n < w + 5:
            return []

        for idx in range(w, n - p["max_hold_ticks"] - 1):
            # No chasing in the final 60s.
            if market.rem_sec[idx] < 60.0:
                continue

            d = market.delta_pct[idx]
            if abs(d) < p["min_delta"]:
                continue
            side = "YES" if d > 0 else "NO"

            prices = market.price_up if side == "YES" else market.price_down
            if np.isnan(prices[idx]) or np.isnan(prices[idx - w]):
                continue
            origin = float(prices[idx - w])
            current = float(prices[idx])
            change = current - origin

            # Alert: fast move >= alert_thresh in chase_window.
            if abs(change) < p["alert_thresh"]:
                continue
            if np.sign(change) != (np.sign(d) if side == 'YES' else -np.sign(d)):
                continue

            # Only chase the early leg: current price within origin_slop of origin.
            if abs(current - origin) > p["origin_slop"]:
                continue

            ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
            if np.isnan(ask) or ask <= 0 or ask > p["max_price"]:
                continue

            exit_idx = self._find_exit(market, idx, side, ask, origin, p)
            reason = (
                f"prob_change_chase side={side} change={change:.3f} "
                f"origin={origin:.3f} ask={ask:.3f}"
            )
            return [Signal(side=side, entry_idx=idx, exit_idx=exit_idx, reason=reason)]

        return []

    def _find_exit(
        self,
        market: Market,
        entry_idx: int,
        side: str,
        entry_price: float,
        origin: float,
        p: dict,
    ) -> Optional[int]:
        n = len(market)
        max_j = min(n - 1, entry_idx + p["max_hold_ticks"])
        prices = market.price_up if side == "YES" else market.price_down
        best_bid = market.best_bid_up if side == "YES" else market.best_bid_down

        for j in range(entry_idx + 1, max_j + 1):
            if market.rem_sec[j] < 1.0:
                return j

            bid = best_bid[j]
            if np.isnan(bid):
                continue

            move = bid - entry_price
            if move >= p["take_profit"]:
                return j

            # Hard invalidation: any single counter-tick >= counter_tick_exit.
            if j > entry_idx + 1 and not np.isnan(prices[j]) and not np.isnan(prices[j - 1]):
                tick = prices[j] - prices[j - 1]
                if side == "YES" and tick <= -p["counter_tick_exit"]:
                    return j
                if side == "NO" and tick >= p["counter_tick_exit"]:
                    return j

            # Do not let the price wander back to the move origin.
            if side == "YES" and prices[j] <= origin:
                return j
            if side == "NO" and prices[j] >= origin:
                return j

        return max_j

    def param_sweep(self):
        for cw in [8, 10, 12]:
            for at in [0.03, 0.04, 0.05]:
                for os in [0.05, 0.07]:
                    for cte in [0.015, 0.025]:
                        for tp in [0.05, 0.08]:
                            for mp in [0.65, 0.75]:
                                yield {
                                    "chase_window": cw,
                                    "alert_thresh": at,
                                    "origin_slop": os,
                                    "counter_tick_exit": cte,
                                    "take_profit": tp,
                                    "min_delta": 0.0001,
                                    "max_price": mp,
                                    "max_hold_ticks": 60,
                                }, f"cw{cw}_at{at}_os{os}_cte{cte}_tp{tp}_mp{mp}"
