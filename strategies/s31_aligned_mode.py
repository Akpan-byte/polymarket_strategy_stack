"""Strategy 31: ALIGNED Mode.
Spot-strike direction and token velocity must agree.
"""
import numpy as np
from typing import List
from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S31AlignedMode(Strategy):
    name = "S31_ALIGNED_Mode"

    def __init__(self, vel_window: int = 4, min_vel: float = 0.01,
                 min_delta: float = 0.0002, max_price: float = 0.70):
        self.params = {
            "vel_window": vel_window,
            "min_vel": min_vel,
            "min_delta": min_delta,
            "max_price": max_price,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        if n < p["vel_window"] + 2:
            return []

        # Skip first minute and last 10s
        for idx in range(60, n - 10):
            d = market.delta_pct[idx]
            if abs(d) < p["min_delta"]:
                continue
            side = "YES" if d > 0 else "NO"

            # Token velocity over last vel_window readings
            if idx < p["vel_window"]:
                continue
            prices = market.price_up if side == "YES" else market.price_down
            window = prices[idx - p["vel_window"]:idx + 1]
            if np.isnan(window).any():
                continue
            vel = float(window[-1] - window[0])
            if abs(vel) < p["min_vel"]:
                continue
            if np.sign(vel) != (np.sign(d) if side == 'YES' else -np.sign(d)):
                continue

            ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
            if np.isnan(ask) or ask > p["max_price"]:
                continue

            return [Signal(side=side, entry_idx=idx, reason=f"aligned vel={vel:.3f} delta={d:.4%}")]
        return []

    def param_sweep(self):
        for vw in [3, 4, 5]:
            for mv in [0.005, 0.01, 0.015]:
                for md in [0.0001, 0.0002, 0.0003]:
                    for mp in [0.60, 0.70, 0.80]:
                        yield {
                            "vel_window": vw,
                            "min_vel": mv,
                            "min_delta": md,
                            "max_price": mp,
                        }, f"vw{vw}_mv{mv}_md{md}_mp{mp}"
