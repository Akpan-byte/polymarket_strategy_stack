"""Strategy 48: Velocity-Flip Reversal.
Fade a move when the spot's rolling velocity flips from strongly positive to
strongly negative (or vice versa), indicating a momentum exhaustion reversal.
"""
import numpy as np
from typing import List

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S48VelocityFlipReversal(Strategy):
    name = "S48_VelocityFlip_Reversal"

    def __init__(
        self,
        vel_window: int = 5,
        pre_threshold: float = 0.0005,
        post_threshold: float = 0.0003,
        max_price: float = 0.70,
    ):
        self.params = {
            "vel_window": vel_window,
            "pre_threshold": pre_threshold,
            "post_threshold": post_threshold,
            "max_price": max_price,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        vw = p["vel_window"]
        if n < 2 * vw + 5:
            return []

        deltas = market.delta_pct

        for idx in range(2 * vw, n - 10):
            prior = float(deltas[idx - vw] - deltas[idx - 2 * vw])
            current = float(deltas[idx] - deltas[idx - vw])

            side = None
            # Strong up velocity then negative flip -> fade to NO.
            if prior > p["pre_threshold"] and current < -p["post_threshold"]:
                side = "NO"
            # Strong down velocity then positive flip -> fade to YES.
            elif prior < -p["pre_threshold"] and current > p["post_threshold"]:
                side = "YES"

            if side is None:
                continue

            ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
            if np.isnan(ask) or ask > p["max_price"]:
                continue

            return [
                Signal(
                    side=side,
                    entry_idx=idx,
                    reason=(
                        f"velocity_flip side={side} prior={prior:.4%} "
                        f"current={current:.4%}"
                    ),
                )
            ]

        return []

    def param_sweep(self):
        for vw in [4, 5, 6]:
            for pt in [0.0004, 0.0005, 0.0006]:
                for pst in [0.0002, 0.0003, 0.0004]:
                    for mp in [0.60, 0.70, 0.80]:
                        yield {
                            "vel_window": vw,
                            "pre_threshold": pt,
                            "post_threshold": pst,
                            "max_price": mp,
                        }, f"vw{vw}_pt{pt}_pst{pst}_mp{mp}"
