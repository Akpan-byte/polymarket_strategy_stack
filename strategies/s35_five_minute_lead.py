"""Strategy 35: 5m Lead for 15m Entry.
Use the early portion of the window as a directional "lead", then enter once
that direction is confirmed for a short follow-through period.  In the
5-minute BTC window data this adapts naturally: the "5m lead" becomes the
initial lead segment of the current window and the position is held to
resolution.
"""
import numpy as np
from typing import List
from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S35FiveMinuteLead(Strategy):
    name = "S35_5m_Lead_15m_Entry"

    def __init__(self, lead_sec: float = 120.0, confirm_sec: float = 60.0,
                 min_lead_move: float = 0.015, min_confirm_move: float = 0.005,
                 min_delta: float = 0.0003, max_price: float = 0.75):
        self.params = {
            "lead_sec": lead_sec,
            "confirm_sec": confirm_sec,
            "min_lead_move": min_lead_move,
            "min_confirm_move": min_confirm_move,
            "min_delta": min_delta,
            "max_price": max_price,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        if n < 10:
            return []

        lead_idx = int(np.searchsorted(market.elapsed_sec, p["lead_sec"], side="left"))
        if lead_idx >= n - 5 or lead_idx < 2:
            return []

        # Measure the lead-period move.
        for side, prices in (("YES", market.price_up), ("NO", market.price_down)):
            if np.isnan(prices[:lead_idx + 1]).any():
                continue
            lead_move = float(prices[lead_idx] - prices[0])
            if abs(lead_move) < p["min_lead_move"]:
                continue
            expected_side = "YES" if lead_move > 0 else "NO"
            if side != expected_side:
                continue

            # Look for confirmation in the following confirm_sec window.
            confirm_end = int(np.searchsorted(
                market.elapsed_sec,
                market.elapsed_sec[lead_idx] + p["confirm_sec"],
                side="right",
            ))
            confirm_end = min(confirm_end, n - 5)
            if confirm_end <= lead_idx + 1:
                continue

            for idx in range(lead_idx + 1, confirm_end + 1):
                d = market.delta_pct[idx]
                if abs(d) < p["min_delta"]:
                    continue
                if (d > 0 and side != "YES") or (d < 0 and side != "NO"):
                    continue

                confirm_move = float(prices[idx] - prices[lead_idx])
                if side == "YES" and confirm_move < p["min_confirm_move"]:
                    continue
                if side == "NO" and confirm_move > -p["min_confirm_move"]:
                    continue

                ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
                if np.isnan(ask) or ask > p["max_price"]:
                    continue

                return [Signal(
                    side=side,
                    entry_idx=idx,
                    reason=f"5m_lead lead_move={lead_move:.3f} confirm={confirm_move:.3f}",
                )]
        return []

    def param_sweep(self):
        for ls in [90.0, 120.0, 150.0]:
            for cs in [30.0, 60.0, 90.0]:
                for lm in [0.010, 0.015, 0.020]:
                    for cm in [0.003, 0.005, 0.008]:
                        for md in [0.0002, 0.0003]:
                            for mp in [0.65, 0.75]:
                                yield {
                                    "lead_sec": ls,
                                    "confirm_sec": cs,
                                    "min_lead_move": lm,
                                    "min_confirm_move": cm,
                                    "min_delta": md,
                                    "max_price": mp,
                                }, f"ls{int(ls)}_cs{int(cs)}_lm{lm}_cm{cm}_md{md}_mp{mp}"
