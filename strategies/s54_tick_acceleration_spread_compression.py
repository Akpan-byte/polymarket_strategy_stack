"""Strategy 54: Tick Acceleration + Spread-Compression Timing Entry.
Fire when the chosen-side spread compresses, velocity is rising, and the spot
has not already consumed most of its expected move.
"""
import numpy as np
from typing import List

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S54TickAccelerationSpreadCompression(Strategy):
    name = "S54_Tick_Acceleration_Spread_Compression"

    def __init__(
        self,
        window: int = 30,
        min_delta: float = 0.0002,
        spread_compress_pct: float = 0.25,
        spread_cancel_pct: float = 0.60,
        velocity_rise_ticks: int = 3,
        move_used_threshold: float = 0.50,
        max_price: float = 0.70,
    ):
        self.params = {
            "window": window,
            "min_delta": min_delta,
            "spread_compress_pct": spread_compress_pct,
            "spread_cancel_pct": spread_cancel_pct,
            "velocity_rise_ticks": velocity_rise_ticks,
            "move_used_threshold": move_used_threshold,
            "max_price": max_price,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        w = p["window"]
        rise = p["velocity_rise_ticks"]
        if n < max(w, rise) + 5:
            return []

        delta = market.delta_pct

        # Per-side spread arrays
        spread_up = market.best_ask_up - market.best_bid_up
        spread_down = market.best_ask_down - market.best_bid_down

        # Velocity = absolute spot change per elapsed second.
        dt = np.diff(market.elapsed_sec)
        dt = np.where(dt <= 0, 1e-9, dt)
        velocity = np.full(n, np.nan)
        velocity[1:] = np.abs(np.diff(market.spot)) / dt

        # Expected move proxy: largest |delta_pct| observed over the rolling window.
        expected_move = np.full(n, np.nan)
        for idx in range(1, n):
            start = max(0, idx - w + 1)
            seg = delta[start : idx + 1]
            if len(seg) >= 2:
                expected_move[idx] = float(np.max(np.abs(seg)))

        armed = False
        side = None

        for idx in range(max(w, rise), n - 10):
            # Default side from current delta sign.
            cur_side = "YES" if delta[idx] > 0 else "NO"
            spread = spread_up if cur_side == "YES" else spread_down
            cur_spread = float(spread[idx])
            if np.isnan(cur_spread):
                continue

            # Rolling percentile window up to and including idx.
            start = max(0, idx - w + 1)
            hist = spread[start : idx + 1]
            if len(hist) < 2:
                continue
            p_compress = float(np.percentile(hist, p["spread_compress_pct"] * 100))
            p_cancel = float(np.percentile(hist, p["spread_cancel_pct"] * 100))

            ad = abs(delta[idx])

            # State transitions
            if not armed:
                if ad >= p["min_delta"]:
                    armed = True
                    side = cur_side
                else:
                    continue

            # If side flipped or delta collapsed, disarm.
            if ad < p["min_delta"]:
                armed = False
                side = None
                continue

            # Cancel on spread widening past cancel percentile.
            if cur_spread > p_cancel:
                armed = False
                side = None
                continue

            # Fire conditions
            if cur_spread <= p_compress:
                # Velocity rising for >= rise consecutive ticks.
                v_window = velocity[idx - rise + 1 : idx + 1]
                if np.any(np.isnan(v_window)):
                    continue
                if not all(v_window[i] > v_window[i - 1] for i in range(1, len(v_window))):
                    continue

                # Move-used check
                em = expected_move[idx]
                if np.isnan(em) or em <= 1e-12:
                    continue
                move_used = ad / em
                if move_used >= p["move_used_threshold"]:
                    continue

                ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
                if np.isnan(ask) or ask <= 0 or ask >= 1.0 or ask > p["max_price"]:
                    continue

                reason = (
                    f"tick_accel_spread_compress side={side} "
                    f"spread={cur_spread:.4f} p25={p_compress:.4f} "
                    f"vel_rise={rise} move_used={move_used:.2f} ask={ask:.3f}"
                )
                return [Signal(side=side, entry_idx=idx, reason=reason)]

        return []

    def param_sweep(self):
        for window in [20, 30]:
            for min_delta in [0.0001, 0.0002]:
                for rise in [2, 3, 4]:
                    for thr in [0.40, 0.50]:
                        for mp in [0.60, 0.70, 0.80]:
                            yield {
                                "window": window,
                                "min_delta": min_delta,
                                "spread_compress_pct": 0.25,
                                "spread_cancel_pct": 0.60,
                                "velocity_rise_ticks": rise,
                                "move_used_threshold": thr,
                                "max_price": mp,
                            }, f"w{window}_md{min_delta}_r{rise}_thr{thr}_mp{mp}"
