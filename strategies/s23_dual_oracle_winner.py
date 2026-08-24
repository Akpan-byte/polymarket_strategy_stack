"""Strategy 23: Dual-Oracle Confirmed Winner Snipe.
Confirm with spot + synthetic Chainlink; fire only if model edge clears costs.
"""
import math
import numpy as np
from typing import List
from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


def _norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


class S23DualOracleWinner(Strategy):
    name = "S23_DualOracle_Winner"

    def __init__(self, t_start: float = 20.0, t_min: float = 5.0,
                 edge_min: float = 0.03, stale_sec: float = 2.0,
                 vol_window: int = 60):
        self.params = {
            "t_start": t_start,
            "t_min": t_min,
            "edge_min": edge_min,
            "stale_sec": stale_sec,
            "vol_window": vol_window,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        # Look for snapshot near t_start remaining
        mask = (market.rem_sec <= p["t_start"]) & (market.rem_sec >= p["t_min"])
        idxs = np.where(mask)[0]
        if idxs.size == 0:
            return []

        # Use last snapshot in the window for decision
        idx = int(idxs[-1])
        spot = market.spot[idx]
        strike = market.strike
        delta = spot - strike
        side = "YES" if delta > 0 else "NO"

        # Synthetic oracle check: spot and a recent TWAP agree on direction
        t0 = max(0, idx - p["vol_window"])
        twap = float(np.mean(market.spot[t0:idx+1]))
        if (twap - strike) * delta <= 0:
            return []

        # Model prob: binary fair value using short-horizon realized vol
        rets = np.diff(market.spot[t0:idx+1]) / market.spot[t0:idx]
        sigma = float(np.std(rets)) if len(rets) > 1 else 0.001
        t_rem = max(market.rem_sec[idx], 1.0) / 300.0  # fraction of 5-min window
        if sigma <= 1e-9:
            sigma = 0.001
        p_model = _norm_cdf(delta / strike / (sigma * math.sqrt(t_rem)))

        ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
        if np.isnan(ask):
            return []

        # Fee-aware edge
        fee = ask * 0.25 * (ask * (1.0 - ask)) ** 2
        edge = p_model - ask - fee
        if edge < p["edge_min"]:
            return []

        return [Signal(side=side, entry_idx=idx, reason=f"edge={edge:.3f} p={p_model:.3f} ask={ask:.3f}")]

    def param_sweep(self):
        for ts in [15, 20, 25]:
            for tm in [3, 5, 8]:
                for em in [0.02, 0.03, 0.05]:
                    yield {
                        "t_start": ts,
                        "t_min": tm,
                        "edge_min": em,
                        "stale_sec": 2.0,
                        "vol_window": 60,
                    }, f"ts{ts}_tm{tm}_em{em}"
