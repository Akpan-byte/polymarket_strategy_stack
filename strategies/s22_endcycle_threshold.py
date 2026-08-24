"""Strategy 22: Endcycle Threshold Sniper.
Wait until the final seconds of the window and snipe the leading side when
the market has not yet fully priced in an obvious directional outcome.
"""
import numpy as np
from typing import List
from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S22EndcycleThreshold(Strategy):
    name = "S22_EndcycleThreshold_Sniper"

    def __init__(self, t_entry: float = 10.0, t_min: float = 3.0,
                 delta_min: float = 0.0002, ask_min: float = 0.95,
                 twap_window: int = 30):
        self.params = {
            "t_entry": t_entry,
            "t_min": t_min,
            "delta_min": delta_min,
            "ask_min": ask_min,
            "twap_window": twap_window,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        # Look for snapshot near t_entry remaining
        mask = (market.rem_sec <= p["t_entry"]) & (market.rem_sec >= p["t_min"])
        idxs = np.where(mask)[0]
        if idxs.size == 0:
            return []

        # Pick the first qualifying snapshot (still enough time to fill)
        idx = int(idxs[0])
        d = market.delta_pct[idx]
        if abs(d) < p["delta_min"]:
            return []

        side = "YES" if d > 0 else "NO"
        ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
        if np.isnan(ask) or ask < p["ask_min"]:
            return []

        # Synthetic Chainlink/TWAP confirmation: spot TWAP aligns with current delta
        t0 = max(0, idx - p["twap_window"])
        twap = float(np.mean(market.spot[t0:idx + 1]))
        if (twap - market.strike) * d <= 0:
            return []

        return [Signal(side=side, entry_idx=idx,
                       reason=f"endcycle snipe ask={ask:.3f} delta={d:.4%} T-{market.rem_sec[idx]:.1f}s")]

    def param_sweep(self):
        for te in [5, 8, 12, 15]:
            for tm in [1, 2, 3]:
                for dm in [0.0002, 0.0003, 0.0005]:
                    for am in [0.92, 0.95, 0.97]:
                        yield {
                            "t_entry": te,
                            "t_min": tm,
                            "delta_min": dm,
                            "ask_min": am,
                            "twap_window": 30,
                        }, f"te{te}_tm{tm}_dm{dm}_am{am}"
