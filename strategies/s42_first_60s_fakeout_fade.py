"""Strategy 42: First-60s Fakeout Fade.
Fade an early spike/fall inside the first minute when the spot prints an
extreme and then retraces, confirmed by a short TWAP of the spot delta.
"""
import numpy as np
from typing import List

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S42First60sFakeoutFade(Strategy):
    name = "S42_First60s_FakeoutFade"

    def __init__(
        self,
        fakeout_pct: float = 0.0010,
        retrace_pct: float = 0.0005,
        twap_window: int = 5,
        max_price: float = 0.70,
    ):
        self.params = {
            "fakeout_pct": fakeout_pct,
            "retrace_pct": retrace_pct,
            "twap_window": twap_window,
            "max_price": max_price,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        if n < max(3, p["twap_window"]):
            return []

        twap_w = p["twap_window"]
        deltas = market.delta_pct

        for idx in range(twap_w - 1, n):
            # Only trade inside the first 60 seconds.
            if market.elapsed_sec[idx] > 60.0:
                continue

            cur = float(deltas[idx])

            # Short TWAP of delta to confirm momentum direction.
            twap = float(np.mean(deltas[idx - twap_w + 1 : idx + 1]))

            # Look back from the open up to the current bar for an extreme.
            max_d = float(np.max(deltas[: idx + 1]))
            min_d = float(np.min(deltas[: idx + 1]))

            side = None
            # Up fakeout then retracement -> fade by selling YES (NO).
            if max_d >= p["fakeout_pct"] and cur <= max_d - p["retrace_pct"] and twap > cur:
                side = "NO"
            # Down fakeout then bounce -> fade by buying YES.
            elif min_d <= -p["fakeout_pct"] and cur >= min_d + p["retrace_pct"] and twap < cur:
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
                        f"first60s_fakeout side={side} cur={cur:.4%} "
                        f"extreme=({min_d:.4%},{max_d:.4%}) twap={twap:.4%}"
                    ),
                )
            ]

        return []

    def param_sweep(self):
        for fp in [0.0008, 0.0010, 0.0015]:
            for rp in [0.0003, 0.0005, 0.0008]:
                for tw in [3, 5, 7]:
                    for mp in [0.60, 0.70, 0.80]:
                        yield {
                            "fakeout_pct": fp,
                            "retrace_pct": rp,
                            "twap_window": tw,
                            "max_price": mp,
                        }, f"fp{fp}_rp{rp}_tw{tw}_mp{mp}"
