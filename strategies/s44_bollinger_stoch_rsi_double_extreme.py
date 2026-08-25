"""Strategy 44: Bollinger + Stochastic RSI Double-Extreme.
Enter a reversal when spot touches a Bollinger Band at the same time Stoch-RSI
crosses out of an extreme zone.
"""
import numpy as np
from typing import List

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S44BollingerStochRsiDoubleExtreme(Strategy):
    name = "S44_Bollinger_Stoch_RSI_Double_Extreme"

    def __init__(
        self,
        bb_window: int = 20,
        bb_std: float = 2.0,
        rsi_window: int = 14,
        stoch_window: int = 14,
        k_period: int = 3,
        d_period: int = 3,
        oversold: float = 20.0,
        overbought: float = 80.0,
        max_price: float = 0.55,
        min_t_rem: float = 90.0,
        skip_expanding_bands: bool = True,
    ):
        self.params = {
            "bb_window": bb_window,
            "bb_std": bb_std,
            "rsi_window": rsi_window,
            "stoch_window": stoch_window,
            "k_period": k_period,
            "d_period": d_period,
            "oversold": oversold,
            "overbought": overbought,
            "max_price": max_price,
            "min_t_rem": min_t_rem,
            "skip_expanding_bands": skip_expanding_bands,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        min_idx = max(p["bb_window"], p["rsi_window"] + p["stoch_window"] + p["k_period"] + p["d_period"]) + 2
        if n < min_idx + 10:
            return []

        spot = market.spot

        # Bollinger Bands on spot (population std), right-aligned.
        cum = np.cumsum(spot)
        cum_sq = np.cumsum(spot ** 2)
        w = p["bb_window"]
        mean = (cum[w - 1:] - np.concatenate(([0.0], cum[: n - w]))) / w
        var = (cum_sq[w - 1:] - np.concatenate(([0.0], cum_sq[: n - w]))) / w - mean ** 2
        var = np.where(var < 0, 0, var)
        std = np.sqrt(var)
        pad = np.full(w - 1, np.nan)
        mean = np.concatenate((pad, mean))
        std = np.concatenate((pad, std))
        upper = mean + p["bb_std"] * std
        lower = mean - p["bb_std"] * std

        # RSI on spot returns (vectorized rolling sums).
        diffs = np.diff(spot)
        gains = np.maximum(diffs, 0.0)
        losses = -np.minimum(diffs, 0.0)
        cum_gain = np.cumsum(gains)
        cum_loss = np.cumsum(losses)
        rw = p["rsi_window"]
        rsi = np.full(n, np.nan)
        g_window = cum_gain[rw:] - cum_gain[:-rw]
        l_window = cum_loss[rw:] - cum_loss[:-rw]
        avg_g = g_window / rw
        avg_l = l_window / rw
        rs = np.where(avg_l > 1e-12, avg_g / avg_l, np.where(avg_g > 1e-12, np.inf, 1.0))
        rsi[rw + 1 :] = np.where(np.isinf(rs), 100.0, 100.0 - 100.0 / (1.0 + rs))

        # Stochastic RSI: (RSI - min RSI) / (max RSI - min RSI) * 100.
        sw = p["stoch_window"]
        stoch_raw = np.full(n, np.nan)
        if n >= sw:
            from numpy.lib.stride_tricks import sliding_window_view
            rsi_slices = sliding_window_view(rsi, sw)
            rmin = np.min(rsi_slices, axis=1)
            rmax = np.max(rsi_slices, axis=1)
            denom = rmax - rmin
            cur = rsi[sw - 1 :]
            stoch_vals = np.where(
                denom <= 1e-12,
                50.0,
                100.0 * (cur - rmin) / denom,
            )
            stoch_raw[sw - 1 :] = stoch_vals

        # %K = SMA(stoch_raw, k_period); %D = SMA(%K, d_period).
        kp = p["k_period"]
        dp = p["d_period"]
        k = self._sma(stoch_raw, kp)
        d = self._sma(k, dp)

        # Band width for expansion check.
        width = upper - lower

        for idx in range(min_idx, n - 10):
            if np.isnan(upper[idx]) or np.isnan(k[idx]) or np.isnan(d[idx]) or np.isnan(k[idx - 1]) or np.isnan(d[idx - 1]):
                continue

            if market.rem_sec[idx] < p["min_t_rem"]:
                continue

            s = spot[idx]
            side = None
            reason_ext = ""

            # UP: price at/below lower band, K crosses above D leaving <20.
            if s <= lower[idx]:
                if k[idx - 1] < d[idx - 1] and k[idx] > d[idx] and k[idx - 1] < p["oversold"]:
                    side = "YES"
                    reason_ext = "lower_band_KcrossD_up"
                    if p["skip_expanding_bands"] and width[idx] > width[idx - 1]:
                        continue

            # DOWN: price at/above upper band, K crosses below D leaving >80.
            elif s >= upper[idx]:
                if k[idx - 1] > d[idx - 1] and k[idx] < d[idx] and k[idx - 1] > p["overbought"]:
                    side = "NO"
                    reason_ext = "upper_band_KcrossD_down"
                    if p["skip_expanding_bands"] and width[idx] > width[idx - 1]:
                        continue

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
                        f"{reason_ext} side={side} spot={s:.2f} "
                        f"bb=({lower[idx]:.2f},{mean[idx]:.2f},{upper[idx]:.2f}) "
                        f"k={k[idx]:.1f} d={d[idx]:.1f}"
                    ),
                )
            ]

        return []

    def _sma(self, x: np.ndarray, window: int) -> np.ndarray:
        """Right-aligned simple moving average."""
        n = len(x)
        out = np.full(n, np.nan)
        if window <= 0 or n < window:
            return out
        cum = np.nancumsum(np.where(np.isnan(x), 0.0, x))
        count = np.cumsum(~np.isnan(x))
        for idx in range(window - 1, n):
            total = cum[idx] - (cum[idx - window] if idx - window >= 0 else 0.0)
            cnt = count[idx] - (count[idx - window] if idx - window >= 0 else 0)
            if cnt > 0:
                out[idx] = total / cnt
        return out

    def param_sweep(self):
        for bbw in [15, 20, 25]:
            for bbs in [1.8, 2.0, 2.2]:
                for rsi in [12, 14, 16]:
                    for mp in [0.50, 0.55]:
                        yield {
                            "bb_window": bbw,
                            "bb_std": bbs,
                            "rsi_window": rsi,
                            "stoch_window": rsi,
                            "k_period": 3,
                            "d_period": 3,
                            "oversold": 20.0,
                            "overbought": 80.0,
                            "max_price": mp,
                            "min_t_rem": 90.0,
                            "skip_expanding_bands": True,
                        }, f"bbw{bbw}_bbs{bbs}_rsi{rsi}_mp{mp}"
