"""Strategy 39: Cross-Window Momentum Continuation.
Require that short-window and long-window token momentum agree in direction,
both clear magnitude thresholds, and the short-window momentum continues (does
not collapse) relative to the long-window move.  This filters spike-and-fade
moves and keeps only sustained directional pressure.
"""
import numpy as np
from typing import List
from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S39CrossWindowMomentum(Strategy):
    name = "S39_Cross_Window_Momentum_Continuation"

    def __init__(self, short_window: int = 5, long_window: int = 15,
                 min_short_vel: float = 0.010, min_long_vel: float = 0.015,
                 continuation_ratio: float = 0.50, min_delta: float = 0.0002,
                 max_price: float = 0.75):
        self.params = {
            "short_window": short_window,
            "long_window": long_window,
            "min_short_vel": min_short_vel,
            "min_long_vel": min_long_vel,
            "continuation_ratio": continuation_ratio,
            "min_delta": min_delta,
            "max_price": max_price,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        start = max(p["long_window"], 10)
        if n < start + 5:
            return []

        for idx in range(start, n - 5):
            d = market.delta_pct[idx]
            if abs(d) < p["min_delta"]:
                continue
            side = "YES" if d > 0 else "NO"
            prices = market.price_up if side == "YES" else market.price_down

            window_short = prices[idx - p["short_window"]:idx + 1]
            window_long = prices[idx - p["long_window"]:idx + 1]
            if np.isnan(window_short).any() or np.isnan(window_long).any():
                continue

            short_vel = float(window_short[-1] - window_short[0])
            long_vel = float(window_long[-1] - window_long[0])

            if abs(short_vel) < p["min_short_vel"]:
                continue
            if abs(long_vel) < p["min_long_vel"]:
                continue
            if np.sign(short_vel) != np.sign(long_vel):
                continue
            if np.sign(short_vel) != (np.sign(d) if side == 'YES' else -np.sign(d)):
                continue

            # Continuation filter: short momentum not fading vs long momentum.
            if abs(long_vel) > 1e-9 and abs(short_vel) < p["continuation_ratio"] * abs(long_vel):
                continue

            ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
            if np.isnan(ask) or ask > p["max_price"]:
                continue

            return [Signal(
                side=side,
                entry_idx=idx,
                reason=f"cross_momentum sv={short_vel:.3f} lv={long_vel:.3f}",
            )]
        return []

    def param_sweep(self):
        for sw in [3, 5, 7]:
            for lw in [10, 15, 20]:
                for msv in [0.010, 0.015]:
                    for mlv in [0.015, 0.020]:
                        for cr in [0.40, 0.60]:
                            for md in [0.0002, 0.0003]:
                                for mp in [0.65, 0.75]:
                                    yield {
                                        "short_window": sw,
                                        "long_window": lw,
                                        "min_short_vel": msv,
                                        "min_long_vel": mlv,
                                        "continuation_ratio": cr,
                                        "min_delta": md,
                                        "max_price": mp,
                                    }, f"sw{sw}_lw{lw}_msv{msv}_mlv{mlv}_cr{cr}_md{md}_mp{mp}"
