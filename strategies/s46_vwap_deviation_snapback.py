"""Strategy 46: VWAP Deviation Snap-Back.
Trade reversion toward a session VWAP from extended deviations; invert on
breakout.  Volume is unavailable, so VWAP is approximated by a time-weighted
average (TWAP) of spot over the lookback window and the sigma bands use a
short rolling standard deviation of spot.
"""
import numpy as np
from typing import List, Tuple

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


def _rolling_mean_std(
    ts: np.ndarray, prices: np.ndarray, window_sec: float
) -> Tuple[np.ndarray, np.ndarray]:
    """Rolling (unweighted) mean and population std over a time window."""
    n = len(ts)
    mean = np.full(n, np.nan, dtype=np.float64)
    std = np.full(n, np.nan, dtype=np.float64)
    for i in range(n):
        left = i
        while left >= 0 and ts[i] - ts[left] <= window_sec:
            left -= 1
        left += 1
        if left < i:
            window = prices[left : i + 1]
            mean[i] = float(np.mean(window))
            std[i] = float(np.std(window))
    return mean, std


class S46VwapDeviationSnapback(Strategy):
    name = "S46_VWAP_Deviation_Snapback"

    def __init__(
        self,
        vwap_window_sec: float = 14400.0,
        sigma_window_sec: float = 60.0,
        entry_dev: float = 1.5,
        exit_dev: float = 0.5,
        breakout_dev: float = 2.5,
        velocity_peak_window: int = 10,
        velocity_decay_pct: float = 0.5,
        min_sigma: float = 1e-6,
        min_rem: float = 120.0,
        final_min_rem: float = 60.0,
        max_price: float = 0.55,
    ):
        self.params = {
            "vwap_window_sec": vwap_window_sec,
            "sigma_window_sec": sigma_window_sec,
            "entry_dev": entry_dev,
            "exit_dev": exit_dev,
            "breakout_dev": breakout_dev,
            "velocity_peak_window": velocity_peak_window,
            "velocity_decay_pct": velocity_decay_pct,
            "min_sigma": min_sigma,
            "min_rem": min_rem,
            "final_min_rem": final_min_rem,
            "max_price": max_price,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        warm_up = max(p["velocity_peak_window"], 2)
        if n < warm_up + 5:
            return []

        # VWAP proxy and 1-min sigma bands on spot.
        vwap, _ = _rolling_mean_std(market.ts, market.spot, p["vwap_window_sec"])
        _, sigma = _rolling_mean_std(market.ts, market.spot, p["sigma_window_sec"])

        valid = sigma > p["min_sigma"]
        dev = np.full(n, np.nan, dtype=np.float64)
        dev[valid] = (market.spot[valid] - vwap[valid]) / sigma[valid]

        # Velocity = absolute change in delta_pct per snapshot.
        velocity = np.full(n, np.nan, dtype=np.float64)
        velocity[1:] = np.abs(np.diff(market.delta_pct))

        # Peak velocity over the recent burst window.
        pv = p["velocity_peak_window"]
        peak_vel = np.full(n, np.nan, dtype=np.float64)
        for i in range(pv - 1, n):
            peak_vel[i] = float(np.nanmax(velocity[i - pv + 1 : i + 1]))

        for idx in range(warm_up, n - 5):
            if (
                np.isnan(dev[idx])
                or np.isnan(velocity[idx])
                or np.isnan(peak_vel[idx])
                or np.isnan(velocity[idx - 1])
            ):
                continue

            adev = abs(dev[idx])
            if adev < p["entry_dev"]:
                continue
            if market.rem_sec[idx] < p["min_rem"]:
                continue

            # Velocity must have decayed at least velocity_decay_pct from peak.
            if velocity[idx] > peak_vel[idx] * (1.0 - p["velocity_decay_pct"]):
                continue

            # Breakout veto: very extended deviation with rising velocity.
            if adev >= p["breakout_dev"] and velocity[idx] > velocity[idx - 1]:
                continue

            # Revert toward VWAP.
            side = "NO" if dev[idx] > 0 else "YES"
            ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
            if np.isnan(ask) or ask > p["max_price"]:
                continue

            # Exit when deviation comes back inside exit_dev, unless we are in
            # the final minute (hold to resolution).
            exit_idx = None
            for j in range(idx + 1, n):
                if not np.isnan(dev[j]) and abs(dev[j]) <= p["exit_dev"]:
                    if market.rem_sec[j] >= p["final_min_rem"]:
                        exit_idx = j
                    break

            reason = (
                f"vwap_snapback side={side} dev={dev[idx]:.2f}s "
                f"vel={velocity[idx]:.4f} peak={peak_vel[idx]:.4f}"
            )
            return [Signal(side=side, entry_idx=idx, exit_idx=exit_idx, reason=reason)]

        return []

    def param_sweep(self):
        for entry_dev in [1.3, 1.5, 1.7]:
            for exit_dev in [0.3, 0.5, 0.7]:
                for max_price in [0.50, 0.55, 0.60]:
                    yield {
                        "vwap_window_sec": 14400.0,
                        "sigma_window_sec": 60.0,
                        "entry_dev": entry_dev,
                        "exit_dev": exit_dev,
                        "breakout_dev": 2.5,
                        "velocity_peak_window": 10,
                        "velocity_decay_pct": 0.5,
                        "min_sigma": 1e-6,
                        "min_rem": 120.0,
                        "final_min_rem": 60.0,
                        "max_price": max_price,
                    }, f"ed{entry_dev}_xd{exit_dev}_mp{max_price}"
