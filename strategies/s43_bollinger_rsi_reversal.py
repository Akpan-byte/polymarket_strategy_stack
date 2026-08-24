"""Strategy 43: Bollinger + RSI Reversal.
Enter against spot extremes when the spot hits a Bollinger Band and RSI
confirms oversold/overbought conditions.
"""
import numpy as np
from typing import List

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S43BollingerRsiReversal(Strategy):
    name = "S43_Bollinger_RSI_Reversal"

    def __init__(
        self,
        bb_window: int = 20,
        bb_std: float = 2.0,
        rsi_window: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        max_price: float = 0.70,
    ):
        self.params = {
            "bb_window": bb_window,
            "bb_std": bb_std,
            "rsi_window": rsi_window,
            "oversold": oversold,
            "overbought": overbought,
            "max_price": max_price,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        min_idx = max(p["bb_window"], p["rsi_window"]) + 1
        if n < min_idx + 5:
            return []

        spot = market.spot

        # Bollinger Bands on spot (population std).
        cum = np.cumsum(spot)
        cum_sq = np.cumsum(spot ** 2)
        w = p["bb_window"]
        mean = (cum[w - 1 :] - np.concatenate(([0.0], cum[: n - w]))) / w
        var = (cum_sq[w - 1 :] - np.concatenate(([0.0], cum_sq[: n - w]))) / w - mean ** 2
        var = np.where(var < 0, 0, var)
        std = np.sqrt(var)
        # Pad so band values align with the right edge of the window.
        pad = np.full(w - 1, np.nan)
        mean = np.concatenate((pad, mean))
        std = np.concatenate((pad, std))
        upper = mean + p["bb_std"] * std
        lower = mean - p["bb_std"] * std

        # RSI on spot returns.
        diffs = np.diff(spot)
        gains = np.maximum(diffs, 0.0)
        losses = -np.minimum(diffs, 0.0)
        cum_gain = np.cumsum(gains)
        cum_loss = np.cumsum(losses)
        rw = p["rsi_window"]
        rsi = np.full(n, np.nan)
        for idx in range(rw + 1, n):
            g = cum_gain[idx - 1] - (cum_gain[idx - rw - 1] if idx - rw - 1 >= 0 else 0.0)
            l = cum_loss[idx - 1] - (cum_loss[idx - rw - 1] if idx - rw - 1 >= 0 else 0.0)
            avg_g = g / rw
            avg_l = l / rw
            if avg_l <= 1e-12:
                rsi[idx] = 100.0 if avg_g > 1e-12 else 50.0
            else:
                rs = avg_g / avg_l
                rsi[idx] = 100.0 - 100.0 / (1.0 + rs)

        for idx in range(min_idx, n - 10):
            if np.isnan(upper[idx]) or np.isnan(rsi[idx]):
                continue

            s = spot[idx]
            side = None
            if s <= lower[idx] and rsi[idx] <= p["oversold"]:
                side = "YES"
            elif s >= upper[idx] and rsi[idx] >= p["overbought"]:
                side = "NO"

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
                        f"bb_rsi_reversal side={side} spot={s:.2f} "
                        f"bb=({lower[idx]:.2f},{upper[idx]:.2f}) rsi={rsi[idx]:.1f}"
                    ),
                )
            ]

        return []

    def param_sweep(self):
        for bw in [15, 20, 25]:
            for bs in [1.8, 2.0, 2.2]:
                for rw in [12, 14, 16]:
                    for mp in [0.60, 0.70, 0.80]:
                        yield {
                            "bb_window": bw,
                            "bb_std": bs,
                            "rsi_window": rw,
                            "oversold": 30.0,
                            "overbought": 70.0,
                            "max_price": mp,
                        }, f"bw{bw}_bs{bs}_rw{rw}_mp{mp}"
