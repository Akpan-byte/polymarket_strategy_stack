"""Strategy 38: Sticky Lagging-Market Convergence.

Single-market proxy for the cross-market idea: when spot has already made a
strong directional move (the "leader"), but the binary market is still priced
cheaply, buy the lagging side and hold toward the implied leader price.
"""
import numpy as np
from typing import List

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S38StickyLaggingMarketConvergence(Strategy):
    name = "S38_Sticky_Lagging_Market_Convergence"

    def __init__(
        self,
        leader_delta: float = 0.002,
        laggard_max: float = 0.80,
        trend_window: int = 5,
        leader_implied: float = 0.95,
        target_offset: float = 0.02,
        min_price: float = 0.02,
    ):
        self.params = {
            "leader_delta": leader_delta,
            "laggard_max": laggard_max,
            "trend_window": trend_window,
            "leader_implied": leader_implied,
            "target_offset": target_offset,
            "min_price": min_price,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        tw = p["trend_window"]
        if n < tw + 5:
            return []

        target = p["leader_implied"] - p["target_offset"]

        for idx in range(tw, n - 5):
            # Spot trend = "underlying moving same direction" filter.
            trend = market.spot[idx] - market.spot[idx - tw]
            if abs(trend) < 1e-12:
                continue

            delta = market.delta_pct[idx]
            if trend > 0:
                side = "YES"
                if delta < p["leader_delta"]:
                    continue
                ask = market.best_ask_up[idx]
            else:
                side = "NO"
                if delta > -p["leader_delta"]:
                    continue
                ask = market.best_ask_down[idx]

            if np.isnan(ask) or ask < p["min_price"] or ask > p["laggard_max"]:
                continue
            # Require enough headroom toward the convergence target.
            if ask >= target:
                continue

            reason = (
                f"sticky_lag side={side} spot_delta={delta:.4%} "
                f"ask={ask:.3f} target={target:.3f} trend={trend:.2f}"
            )
            # Hold to resolution to avoid look-ahead; live execution can
            # schedule the T-15s/target-price exit independently.
            return [Signal(side=side, entry_idx=idx, reason=reason)]

        return []

    def param_sweep(self):
        for ld in [0.0015, 0.0020, 0.0025]:
            for lm in [0.70, 0.80]:
                for tw in [3, 5, 7]:
                    for li in [0.93, 0.95]:
                        yield {
                            "leader_delta": ld,
                            "laggard_max": lm,
                            "trend_window": tw,
                            "leader_implied": li,
                            "target_offset": 0.02,
                            "min_price": 0.02,
                        }, f"ld{ld}_lm{lm}_tw{tw}_li{li}"
