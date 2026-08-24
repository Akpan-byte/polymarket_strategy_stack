"""Strategy 47: Spot-Rebound Lag Reversion.
Fade a spot move that has already reversed direction while the token is still
priced as if the original move is in play. A short spot TWAP confirms the
rebound.
"""
import numpy as np
from typing import List

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S47SpotReboundLagReversion(Strategy):
    name = "S47_SpotRebound_LagReversion"

    def __init__(
        self,
        lookback_window: int = 20,
        trigger_pct: float = 0.0015,
        rebound_pct: float = 0.0010,
        twap_window: int = 5,
        max_price: float = 0.70,
    ):
        self.params = {
            "lookback_window": lookback_window,
            "trigger_pct": trigger_pct,
            "rebound_pct": rebound_pct,
            "twap_window": twap_window,
            "max_price": max_price,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        min_idx = max(p["lookback_window"], p["twap_window"])
        if n < min_idx + 5:
            return []

        lb = p["lookback_window"]
        tw = p["twap_window"]
        deltas = market.delta_pct

        for idx in range(min_idx, n - 10):
            cur = float(deltas[idx])
            window = deltas[idx - lb + 1 : idx + 1]
            past_max = float(np.max(window))
            past_min = float(np.min(window))

            # Short TWAP confirming the rebound direction.
            twap = float(np.mean(deltas[idx - tw + 1 : idx + 1]))

            side = None
            # Spot rallied, then reversed down; token likely still lagging long.
            if past_max >= p["trigger_pct"] and cur <= past_max - p["rebound_pct"] and twap > cur:
                side = "NO"
            # Spot dumped, then reversed up; token likely still lagging short.
            elif past_min <= -p["trigger_pct"] and cur >= past_min + p["rebound_pct"] and twap < cur:
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
                        f"spot_rebound side={side} cur={cur:.4%} "
                        f"past=({past_min:.4%},{past_max:.4%}) twap={twap:.4%}"
                    ),
                )
            ]

        return []

    def param_sweep(self):
        for lb in [15, 20, 25]:
            for tp in [0.0010, 0.0015, 0.0020]:
                for rp in [0.0005, 0.0010, 0.0015]:
                    for tw in [3, 5]:
                        for mp in [0.60, 0.70, 0.80]:
                            yield {
                                "lookback_window": lb,
                                "trigger_pct": tp,
                                "rebound_pct": rp,
                                "twap_window": tw,
                                "max_price": mp,
                            }, f"lb{lb}_tp{tp}_rp{rp}_tw{tw}_mp{mp}"
