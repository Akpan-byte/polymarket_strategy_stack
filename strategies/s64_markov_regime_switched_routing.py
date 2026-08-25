"""Strategy 64: Markov-Regime-Switched Signal Routing.

Classify each moment as TREND / RANGE / NEUTRAL from a 10-minute return,
volatility percentile and Bollinger-bandwidth percentile.  Hysteresis of 3
samples prevents rapid flipping.  Each regime routes to a dedicated engine:
momentum for trends, mean-reversion for ranges, late-window drift for neutral.
"""
import numpy as np
from typing import List

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S64MarkovRegimeSwitchedRouting(Strategy):
    name = "S64_Markov_Regime_Switched_Routing"

    def __init__(
        self,
        return_lookback_sec: float = 600.0,
        trend_return_threshold: float = 0.001,
        vol_window: int = 5,
        vol_percentile_threshold: float = 70.0,
        bb_window: int = 5,
        bb_std: float = 2.0,
        bandwidth_percentile_threshold: float = 70.0,
        hysteresis: int = 3,
        max_price: float = 0.70,
        late_window_sec: float = 30.0,
    ):
        self.params = {
            "return_lookback_sec": return_lookback_sec,
            "trend_return_threshold": trend_return_threshold,
            "vol_window": vol_window,
            "vol_percentile_threshold": vol_percentile_threshold,
            "bb_window": bb_window,
            "bb_std": bb_std,
            "bandwidth_percentile_threshold": bandwidth_percentile_threshold,
            "hysteresis": hysteresis,
            "max_price": max_price,
            "late_window_sec": late_window_sec,
        }

    def _rolling_std(self, x: np.ndarray, w: int) -> np.ndarray:
        """Population std with NaN padding at the left."""
        n = len(x)
        if n < w:
            return np.full(n, np.nan)
        c = np.cumsum(x)
        c2 = np.cumsum(x * x)
        mean = (c[w - 1 :] - np.concatenate(([0.0], c[: n - w]))) / w
        var = (c2[w - 1 :] - np.concatenate(([0.0], c2[: n - w]))) / w - mean ** 2
        var = np.where(var < 0, 0, var)
        std = np.sqrt(var)
        return np.concatenate((np.full(w - 1, np.nan), std))

    def _bollinger(self, spot: np.ndarray, w: int, nstd: float):
        """Return (upper, lower, mean, std) arrays aligned to right edge."""
        n = len(spot)
        upper = np.full(n, np.nan)
        lower = np.full(n, np.nan)
        mean = np.full(n, np.nan)
        std = np.full(n, np.nan)
        if n < w:
            return upper, lower, mean, std
        cum = np.cumsum(spot)
        cum2 = np.cumsum(spot * spot)
        m = (cum[w - 1 :] - np.concatenate(([0.0], cum[: n - w]))) / w
        var = (cum2[w - 1 :] - np.concatenate(([0.0], cum2[: n - w]))) / w - m ** 2
        var = np.where(var < 0, 0, var)
        s = np.sqrt(var)
        pad = np.full(w - 1, np.nan)
        mean = np.concatenate((pad, m))
        std = np.concatenate((pad, s))
        upper = mean + nstd * std
        lower = mean - nstd * std
        return upper, lower, mean, std

    def _percentile_live(self, arr: np.ndarray, w: int) -> np.ndarray:
        """Percentile of current value within trailing window of length w."""
        n = len(arr)
        out = np.full(n, np.nan)
        for i in range(w - 1, n):
            win = arr[i - w + 1 : i + 1]
            win = win[~np.isnan(win)]
            if len(win) == 0:
                continue
            out[i] = 100.0 * np.sum(win < arr[i]) / len(win)
        return out

    def _regimes(self, market: Market) -> np.ndarray:
        p = self.params
        n = len(market)
        elapsed = market.elapsed_sec
        spot = market.spot

        # 10-minute return (falls back to earliest available sample)
        ret_idx = np.zeros(n, dtype=int)
        j = 0
        for i in range(n):
            while j < i and elapsed[i] - elapsed[j] > p["return_lookback_sec"]:
                j += 1
            ret_idx[i] = j
        ret10 = np.where(
            spot[ret_idx] != 0,
            (spot - spot[ret_idx]) / spot[ret_idx],
            0.0,
        )

        # Volatility = std of spot returns over vol_window
        returns = np.diff(spot, prepend=spot[0])
        vol = self._rolling_std(returns, p["vol_window"])
        vw = max(p["vol_window"], 3)
        vol_pct = self._percentile_live(vol, vw) if n >= vw else np.full(n, np.nan)

        # Bollinger bandwidth percentile
        upper, lower, mean, std = self._bollinger(spot, p["bb_window"], p["bb_std"])
        with np.errstate(divide="ignore", invalid="ignore"):
            bandwidth = (upper - lower) / mean
        bandwidth[mean == 0] = 0.0
        bw_win = max(p["bb_window"], 3)
        bw_pct = self._percentile_live(bandwidth, bw_win) if n >= bw_win else np.full(n, np.nan)

        # Raw regime classification
        raw = np.full(n, "NEUTRAL", dtype=object)
        min_idx = max(vw, bw_win, p["bb_window"], p["vol_window"])
        for i in range(min_idx, n):
            high_vol = not np.isnan(vol_pct[i]) and vol_pct[i] >= p["vol_percentile_threshold"]
            high_bw = not np.isnan(bw_pct[i]) and bw_pct[i] >= p["bandwidth_percentile_threshold"]
            trend = abs(ret10[i]) >= p["trend_return_threshold"]

            if trend and high_vol:
                raw[i] = "TREND"
            elif high_bw or (not trend and high_vol):
                # Wide bands / elevated volatility without directional drift -> range
                raw[i] = "RANGE"
            else:
                raw[i] = "NEUTRAL"

        # Hysteresis: require `hysteresis` consecutive raw labels before switching
        regimes = np.full(n, "NEUTRAL", dtype=object)
        current = "NEUTRAL"
        streak = 0
        for i in range(min_idx, n):
            if raw[i] == current:
                streak = 0
            else:
                streak += 1
                if streak >= p["hysteresis"]:
                    current = raw[i]
                    streak = 0
            regimes[i] = current

        return regimes

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        min_needed = max(p["vol_window"], p["bb_window"], p["hysteresis"]) + 2
        if n < min_needed:
            return []

        regimes = self._regimes(market)
        spot = market.spot
        rem = market.rem_sec
        delta = market.delta_pct
        elapsed = market.elapsed_sec

        upper, lower, _, _ = self._bollinger(spot, p["bb_window"], p["bb_std"])

        for idx in range(min_needed, n):
            regime = regimes[idx]
            side = None
            reason = ""

            if regime == "TREND":
                # Momentum: follow return direction over return_lookback_sec
                look = idx
                while look > 0 and elapsed[idx] - elapsed[look] < p["return_lookback_sec"]:
                    look -= 1
                ret = (spot[idx] - spot[look]) / spot[look] if spot[look] != 0 else 0.0
                if abs(ret) < p["trend_return_threshold"]:
                    continue
                side = "YES" if ret > 0 else "NO"
                reason = f"trend momentum ret={ret:.4%} regime={regime}"

            elif regime == "RANGE":
                # Reversion: touch Bollinger band
                if np.isnan(upper[idx]) or np.isnan(lower[idx]):
                    continue
                if spot[idx] >= upper[idx]:
                    side = "NO"
                    reason = f"range reversion spot={spot[idx]:.2f}>=upper={upper[idx]:.2f}"
                elif spot[idx] <= lower[idx]:
                    side = "YES"
                    reason = f"range reversion spot={spot[idx]:.2f}<=lower={lower[idx]:.2f}"
                else:
                    continue

            else:  # NEUTRAL -> late-window drift
                if rem[idx] > p["late_window_sec"]:
                    continue
                if delta[idx] > 0:
                    side = "YES"
                elif delta[idx] < 0:
                    side = "NO"
                else:
                    continue
                reason = f"neutral late-window T-{rem[idx]:.1f}s delta={delta[idx]:.4%}"

            if side is None:
                continue

            ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
            if np.isnan(ask) or ask <= 0 or ask > p["max_price"]:
                continue

            return [Signal(side=side, entry_idx=idx, reason=reason)]

        return []

    def param_sweep(self):
        for trend_th in [0.0008, 0.001, 0.0015]:
            for vol_pct in [60.0, 70.0, 80.0]:
                for bw_pct in [60.0, 70.0, 80.0]:
                    for bbw in [4, 5, 6]:
                        yield {
                            "return_lookback_sec": 600.0,
                            "trend_return_threshold": trend_th,
                            "vol_window": 5,
                            "vol_percentile_threshold": vol_pct,
                            "bb_window": bbw,
                            "bb_std": 2.0,
                            "bandwidth_percentile_threshold": bw_pct,
                            "hysteresis": 3,
                            "max_price": 0.70,
                            "late_window_sec": 30.0,
                        }, f"trend{trend_th}_vol{vol_pct}_bw{bw_pct}_bbw{bbw}"
