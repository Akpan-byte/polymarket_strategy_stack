"""Strategy 24: TWAP Reversal.
Trade mean reversion when the live spot deviates from a recent spot TWAP
(proxy for a slower Chainlink oracle).  Buy the underdog side when the
deviation looks overextended relative to recent volatility.
"""
import numpy as np
from typing import List
from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S24TwapReversal(Strategy):
    name = "S24_TWAP_Reversal"

    def __init__(self, twap_window: int = 60, z_min: float = 1.0,
                 max_price: float = 0.45, min_rem: float = 15.0,
                 vol_window: int = 30):
        self.params = {
            "twap_window": twap_window,
            "z_min": z_min,
            "max_price": max_price,
            "min_rem": min_rem,
            "vol_window": vol_window,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        if n < p["twap_window"] + p["vol_window"] + 2:
            return []

        for idx in range(p["twap_window"] + p["vol_window"], n - 5):
            if market.rem_sec[idx] < p["min_rem"]:
                continue

            # TWAP up to idx
            t0 = max(0, idx - p["twap_window"])
            twap = float(np.mean(market.spot[t0:idx + 1]))

            # Realized vol for z-score
            v0 = max(0, idx - p["vol_window"])
            rets = np.diff(market.spot[v0:idx + 1]) / market.spot[v0:idx]
            sigma = float(np.std(rets)) if len(rets) > 1 else 1e-6
            if sigma <= 1e-9:
                continue

            z = (market.spot[idx] - twap) / market.strike / sigma
            if abs(z) < p["z_min"]:
                continue

            # Contrarian side: expect spot to revert toward TWAP
            side = "NO" if z > 0 else "YES"
            ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
            if np.isnan(ask) or ask > p["max_price"]:
                continue

            return [Signal(side=side, entry_idx=idx,
                           reason=f"twap_reversal z={z:.2f} twap={twap:.1f} ask={ask:.3f}")]
        return []

    def param_sweep(self):
        for tw in [40, 60, 90]:
            for zm in [0.8, 1.0, 1.25]:
                for mp in [0.35, 0.45, 0.55]:
                    for mr in [10, 15, 20]:
                        yield {
                            "twap_window": tw,
                            "z_min": zm,
                            "max_price": mp,
                            "min_rem": mr,
                            "vol_window": 30,
                        }, f"tw{tw}_zm{zm}_mp{mp}_mr{mr}"
