"""Strategy 66: 7-Trigger Priority Exit Stack.
A simple momentum entry paired with a priority-ordered stack of exit triggers
evaluated every snapshot.  The stack handles take-profit, stop-loss, gap
protection, velocity reversal, trailing stop, time-decay floor, and model
invalidation.
"""
import numpy as np
from typing import List, Optional

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S66SevenTriggerExitStack(Strategy):
    name = "S66_SevenTrigger_ExitStack"

    def __init__(
        self,
        vel_window: int = 5,
        min_delta: float = 0.0002,
        min_vel: float = 0.010,
        max_price: float = 0.70,
        sl_calm: float = 0.08,
        sl_volatile: float = 0.13,
        vel_spike: float = 0.04,
        trail_low: float = 0.03,
        trail_high: float = 0.06,
        max_hold_ticks: int = 120,
    ):
        self.params = {
            "vel_window": vel_window,
            "min_delta": min_delta,
            "min_vel": min_vel,
            "max_price": max_price,
            "sl_calm": sl_calm,
            "sl_volatile": sl_volatile,
            "vel_spike": vel_spike,
            "trail_low": trail_low,
            "trail_high": trail_high,
            "max_hold_ticks": max_hold_ticks,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        vw = p["vel_window"]
        if n < vw + 5:
            return []

        for idx in range(vw, n - p["max_hold_ticks"] - 1):
            d = market.delta_pct[idx]
            if abs(d) < p["min_delta"]:
                continue
            side = "YES" if d > 0 else "NO"

            prices = market.price_up if side == "YES" else market.price_down
            if np.isnan(prices[idx]) or np.isnan(prices[idx - vw]):
                continue
            vel = float(prices[idx] - prices[idx - vw])
            if abs(vel) < p["min_vel"]:
                continue
            if np.sign(vel) != np.sign(d):
                continue

            ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
            if np.isnan(ask) or ask <= 0 or ask > p["max_price"]:
                continue

            exit_idx = self._find_exit(market, idx, side, ask, p)
            reason = (
                f"seven_trigger side={side} vel={vel:.4f} ask={ask:.3f} delta={d:.4%}"
            )
            return [Signal(side=side, entry_idx=idx, exit_idx=exit_idx, reason=reason)]

        return []

    def _find_exit(
        self,
        market: Market,
        entry_idx: int,
        side: str,
        entry_price: float,
        p: dict,
    ) -> Optional[int]:
        n = len(market)
        max_j = min(n - 1, entry_idx + p["max_hold_ticks"])

        prices = market.price_up if side == "YES" else market.price_down
        best_bid = market.best_bid_up if side == "YES" else market.best_bid_down

        # Regime-dependent stop width: use recent volatility as a calm/volatile proxy.
        rets = np.diff(market.spot[max(0, entry_idx - 60):entry_idx + 1]) / market.spot[max(0, entry_idx - 60):entry_idx]
        rv = float(np.std(rets)) if len(rets) > 1 else 0.0
        sl_width = p["sl_volatile"] if rv >= 0.0003 else p["sl_calm"]

        peak_price = entry_price
        consec_counter = 0

        for j in range(entry_idx + 1, max_j + 1):
            if market.rem_sec[j] < 1.0:
                return j

            bid = best_bid[j]
            if np.isnan(bid):
                continue

            unreal = bid - entry_price
            max_payout = 1.0 - entry_price

            # 1. Take profit: 45% of max payout.
            if unreal >= 0.45 * max_payout:
                return j

            # 2. Stop loss: regime-dependent width.
            if unreal <= -sl_width:
                return j

            # Update peak for trailing stop.
            if side == "YES":
                peak_price = max(peak_price, bid)
            else:
                peak_price = min(peak_price, bid)

            # 3. Velocity spike: any single tick >= vel_spike / s against the trade.
            if j > entry_idx + 1 and not np.isnan(prices[j]) and not np.isnan(prices[j - 1]):
                dt = max(market.ts[j] - market.ts[j - 1], 1e-9)
                tick = (prices[j] - prices[j - 1]) / dt
                if side == "YES" and tick <= -p["vel_spike"]:
                    return j
                if side == "NO" and tick >= p["vel_spike"]:
                    return j

            # 4. Velocity reversal: 3 consecutive counter-ticks while profitable.
            if j > entry_idx + 1 and not np.isnan(prices[j]) and not np.isnan(prices[j - 1]):
                tick = prices[j] - prices[j - 1]
                counter = (side == "YES" and tick < 0) or (side == "NO" and tick > 0)
                if counter and unreal > 0:
                    consec_counter += 1
                else:
                    consec_counter = 0
                if consec_counter >= 3:
                    return j

            # 5. Trail stop: retreat from peak.
            trail = p["trail_low"] if entry_price < 0.50 else p["trail_high"]
            if side == "YES" and peak_price - bid >= trail:
                return j
            if side == "NO" and bid - peak_price >= trail:
                return j

            # 6. Time floor: ratchet down minimum acceptable unrealized PnL.
            rem = market.rem_sec[j]
            if 60.0 < rem <= 120.0 and unreal < 0.30 * max_payout:
                return j
            if rem <= 60.0 and unreal < 0.15 * max_payout:
                return j

            # 7. Model/delta flip: spot delta sign reverses from entry.
            if np.sign(market.delta_pct[j]) != np.sign(market.delta_pct[entry_idx]):
                return j

        return max_j

    def param_sweep(self):
        for vw in [4, 5, 6]:
            for md in [0.0001, 0.0002]:
                for mv in [0.008, 0.012]:
                    for mp in [0.60, 0.70, 0.80]:
                        for sc in [0.07, 0.09]:
                            for sv in [0.11, 0.15]:
                                yield {
                                    "vel_window": vw,
                                    "min_delta": md,
                                    "min_vel": mv,
                                    "max_price": mp,
                                    "sl_calm": sc,
                                    "sl_volatile": sv,
                                    "vel_spike": 0.04,
                                    "trail_low": 0.03,
                                    "trail_high": 0.06,
                                    "max_hold_ticks": 120,
                                }, f"vw{vw}_md{md}_mv{mv}_mp{mp}_sc{sc}_sv{sv}"
