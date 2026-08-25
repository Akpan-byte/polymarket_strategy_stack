"""Strategy 50: Band-Width Squeeze -> Expansion Breakout.
Arm when Bollinger bandwidth is at a trailing-window low; fire on the first
close outside the band when spot velocity surges. Exit if the breakout is
rejected and price closes back inside the band.
"""
import numpy as np
from typing import List, Optional

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S50BollingerSqueezeBreakout(Strategy):
    name = "S50_Bollinger_Squeeze_Breakout"

    def __init__(
        self,
        bb_window: int = 20,
        bb_std: float = 2.0,
        bandwidth_window: int = 60,
        bandwidth_pctile: float = 20.0,
        velocity_lookback: int = 1,
        velocity_window: int = 10,
        velocity_multiplier: float = 1.5,
        max_price: float = 0.60,
        min_rem_sec: float = 90.0,
        max_squeeze_hours: float = 6.0,
    ):
        self.params = {
            "bb_window": bb_window,
            "bb_std": bb_std,
            "bandwidth_window": bandwidth_window,
            "bandwidth_pctile": bandwidth_pctile,
            "velocity_lookback": velocity_lookback,
            "velocity_window": velocity_window,
            "velocity_multiplier": velocity_multiplier,
            "max_price": max_price,
            "min_rem_sec": min_rem_sec,
            "max_squeeze_hours": max_squeeze_hours,
        }

    def _bollinger_bands(self, spot: np.ndarray, w: int, k: float):
        n = len(spot)
        cum = np.cumsum(spot)
        cum_sq = np.cumsum(spot ** 2)
        mean = (cum[w - 1:] - np.concatenate(([0.0], cum[: n - w]))) / w
        var = (cum_sq[w - 1:] - np.concatenate(([0.0], cum_sq[: n - w]))) / w - mean ** 2
        var = np.where(var < 0, 0, var)
        std = np.sqrt(var)
        pad = np.full(w - 1, np.nan)
        mean = np.concatenate((pad, mean))
        std = np.concatenate((pad, std))
        upper = mean + k * std
        lower = mean - k * std
        bandwidth = upper - lower
        return mean, upper, lower, bandwidth

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        w = p["bb_window"]
        min_idx = w + max(p["bandwidth_window"], p["velocity_window"]) + p["velocity_lookback"] + 1
        if n < min_idx + 10:
            return []

        spot = market.spot
        mean, upper, lower, bandwidth = self._bollinger_bands(spot, w, p["bb_std"])

        # Trailing bandwidth percentile (vectorized rolling window).
        bw_window = p["bandwidth_window"]
        bw_pctile = p["bandwidth_pctile"]
        bw_threshold = np.full(n, np.nan)
        if n >= w + bw_window:
            from numpy.lib.stride_tricks import sliding_window_view
            bw_slices = sliding_window_view(bandwidth, bw_window)
            # Align so threshold[idx] uses bandwidth[idx-bw_window+1 : idx+1]
            bw_vals = np.nanpercentile(bw_slices, bw_pctile, axis=1)
            bw_threshold[w + bw_window - 1 :] = bw_vals[w + bw_window - 1 - bw_window + 1 :]

        # Spot velocity (absolute move over lookback) and trailing mean of prior bars
        vl = p["velocity_lookback"]
        velocity = np.full(n, np.nan)
        velocity[vl:] = np.abs(spot[vl:] - spot[:-vl])
        vw = p["velocity_window"]
        mean_velocity = np.full(n, np.nan)
        if n >= vl + vw:
            vel_slices = sliding_window_view(velocity, vw)
            mean_velocity[vl + vw - 1 :] = np.nanmean(vel_slices[vl + vw - 1 - vw + 1 :], axis=1)

        # Bar duration for squeeze timeout (seconds per bar)
        sec_per_bar = np.median(np.diff(market.ts))
        if sec_per_bar <= 0:
            sec_per_bar = 300.0
        max_squeeze_bars = int(p["max_squeeze_hours"] * 3600.0 / sec_per_bar)

        signals: List[Signal] = []
        armed_idx: Optional[int] = None

        for idx in range(min_idx, n - 1):
            if np.isnan(upper[idx]) or np.isnan(bw_threshold[idx]):
                continue

            # Arm on bandwidth squeeze
            if bandwidth[idx] <= bw_threshold[idx] and armed_idx is None:
                armed_idx = idx

            if armed_idx is None:
                continue

            # Disarm after max squeeze duration with no trigger
            if idx - armed_idx > max_squeeze_bars:
                armed_idx = None
                continue

            # Trigger: close outside band with velocity surge
            s = spot[idx]
            side = None
            if s > upper[idx]:
                side = "YES"
            elif s < lower[idx]:
                side = "NO"

            if side is None:
                continue

            if np.isnan(velocity[idx]) or np.isnan(mean_velocity[idx]):
                armed_idx = None
                continue
            if velocity[idx] < p["velocity_multiplier"] * mean_velocity[idx]:
                armed_idx = None
                continue

            # Entry filters
            if market.rem_sec[idx] < p["min_rem_sec"]:
                armed_idx = None
                continue

            ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
            if np.isnan(ask) or ask > p["max_price"]:
                armed_idx = None
                continue

            # False-break exit: close back inside band
            exit_idx = None
            for j in range(idx + 1, n):
                if lower[j] < spot[j] < upper[j]:
                    exit_idx = j
                    break

            reason = (
                f"squeeze_breakout side={side} spot={s:.2f} "
                f"bb=({lower[idx]:.2f},{upper[idx]:.2f}) "
                f"bw={bandwidth[idx]:.4f}<=pct{bw_threshold[idx]:.4f} "
                f"vel={velocity[idx]:.4f}/m{mean_velocity[idx]:.4f}"
            )
            signals.append(Signal(side=side, entry_idx=idx, exit_idx=exit_idx, reason=reason))

            # One attempt per squeeze
            armed_idx = None

        return signals

    def param_sweep(self):
        for bw in [15, 20]:
            for bs in [1.8, 2.2]:
                for bp in [15.0, 25.0]:
                    for vm in [1.3, 1.7]:
                        yield {
                            "bb_window": bw,
                            "bb_std": bs,
                            "bandwidth_window": 60,
                            "bandwidth_pctile": bp,
                            "velocity_lookback": 1,
                            "velocity_window": 10,
                            "velocity_multiplier": vm,
                            "max_price": 0.60,
                            "min_rem_sec": 90.0,
                            "max_squeeze_hours": 6.0,
                        }, f"bw{bw}_bs{bs}_bp{bp}_vm{vm}"
