"""Strategy 32: MOMENTUM Mode.
Enter when token velocity and recent directional persistence agree with the
spot-strike delta.  Designed to catch trending windows and avoid choppy/ranging
markets by requiring sustained ticks in the trade direction.
"""
import numpy as np
from typing import List
from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S32MomentumMode(Strategy):
    name = "S32_MOMENTUM_Mode"

    def __init__(self, vel_window: int = 6, min_vel: float = 0.015,
                 min_delta: float = 0.0003, max_price: float = 0.75,
                 sustain_ticks: int = 3):
        self.params = {
            "vel_window": vel_window,
            "min_vel": min_vel,
            "min_delta": min_delta,
            "max_price": max_price,
            "sustain_ticks": sustain_ticks,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        start = max(p["vel_window"] + p["sustain_ticks"], 10)
        if n < start + 5:
            return []

        for idx in range(start, n - 5):
            d = market.delta_pct[idx]
            if abs(d) < p["min_delta"]:
                continue
            side = "YES" if d > 0 else "NO"
            prices = market.price_up if side == "YES" else market.price_down

            # Velocity over the lookback window.
            window = prices[idx - p["vel_window"]:idx + 1]
            if np.isnan(window).any():
                continue
            vel = float(window[-1] - window[0])
            if abs(vel) < p["min_vel"] or np.sign(vel) != (np.sign(d) if side == 'YES' else -np.sign(d)):
                continue

            # Sustained directional ticks: most recent sustain_ticks moves agree.
            recent = prices[idx - p["sustain_ticks"]:idx + 1]
            diffs = np.diff(recent)
            if side == "YES":
                if int(np.sum(diffs > 0)) < p["sustain_ticks"]:
                    continue
            else:
                if int(np.sum(diffs < 0)) < p["sustain_ticks"]:
                    continue

            ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
            if np.isnan(ask) or ask > p["max_price"]:
                continue

            return [Signal(
                side=side,
                entry_idx=idx,
                reason=f"momentum vel={vel:.3f} delta={d:.4%} sustain={p['sustain_ticks']}",
            )]
        return []

    def param_sweep(self):
        for vw in [4, 6, 8]:
            for mv in [0.010, 0.015, 0.020]:
                for md in [0.0002, 0.0003, 0.0005]:
                    for mp in [0.65, 0.75, 0.85]:
                        for st in [2, 3, 4]:
                            yield {
                                "vel_window": vw,
                                "min_vel": mv,
                                "min_delta": md,
                                "max_price": mp,
                                "sustain_ticks": st,
                            }, f"vw{vw}_mv{mv}_md{md}_mp{mp}_st{st}"
