"""Strategy 40: Cascade Trailing Logic.
Deploy directional tranches in a cascade (probe, widen, time-add, final add),
each carried with a fixed -8c stop from its own entry.  Earlier stops breaking
before a later add cancel the remaining cascade.
"""
import numpy as np
from typing import List, Optional

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S40CascadeTrailingLogic(Strategy):
    name = "S40_Cascade_Trailing_Logic"

    def __init__(
        self,
        entry_delta: float = 0.001,
        t_probe: float = 150.0,
        widen_ratio: float = 0.5,
        t_add_60: float = 60.0,
        t_add_15: float = 15.0,
        stop_cents: float = 0.08,
        fair_discount_cents: float = 0.04,
        max_price: float = 0.70,
    ):
        self.params = {
            "entry_delta": entry_delta,
            "t_probe": t_probe,
            "widen_ratio": widen_ratio,
            "t_add_60": t_add_60,
            "t_add_15": t_add_15,
            "stop_cents": stop_cents,
            "fair_discount_cents": fair_discount_cents,
            "max_price": max_price,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        if n < 10:
            return []

        delta = market.delta_pct
        rem = market.rem_sec
        fair = 0.5

        # --- Tranche 1: probe -------------------------------------------------
        probe_idx = None
        for idx in range(n):
            if rem[idx] <= p["t_probe"] and abs(delta[idx]) >= p["entry_delta"]:
                probe_idx = idx
                break
        if probe_idx is None:
            return []

        side = "YES" if delta[probe_idx] > 0 else "NO"
        side_sign = 1.0 if side == "YES" else -1.0
        entry_delta_abs = abs(delta[probe_idx])

        ask_arr = market.best_ask_up if side == "YES" else market.best_ask_down
        bid_arr = market.best_bid_up if side == "YES" else market.best_bid_down

        probe_ask = float(ask_arr[probe_idx])
        if np.isnan(probe_ask) or probe_ask <= 0 or probe_ask > p["max_price"]:
            return []

        signals = []
        probe_stop = probe_ask - p["stop_cents"]
        probe_exit = self._find_stop_exit(market, probe_idx, side, probe_stop)
        signals.append(
            Signal(
                side=side,
                entry_idx=probe_idx,
                exit_idx=probe_exit,
                reason=(
                    f"cascade_probe side={side} ask={probe_ask:.3f} "
                    f"delta={delta[probe_idx]:.4%} stop={probe_stop:.3f}"
                ),
            )
        )

        # Helper to cancel remaining cascade if any prior stop was hit.
        def prior_stop_hit(before_idx: int) -> bool:
            for sig in signals:
                if sig.exit_idx is None:
                    continue
                if sig.exit_idx <= before_idx:
                    return True
            return False

        # --- Tranche 2: add on delta widening ---------------------------------
        widen_threshold = entry_delta_abs * (1.0 + p["widen_ratio"])
        widen_idx = None
        for idx in range(probe_idx + 1, n):
            if prior_stop_hit(idx):
                break
            if side_sign * delta[idx] > 0 and abs(delta[idx]) >= widen_threshold:
                widen_idx = idx
                break

        if widen_idx is not None:
            widen_ask = float(ask_arr[widen_idx])
            if not (np.isnan(widen_ask) or widen_ask <= 0 or widen_ask > p["max_price"]):
                widen_stop = widen_ask - p["stop_cents"]
                widen_exit = self._find_stop_exit(market, widen_idx, side, widen_stop)
                signals.append(
                    Signal(
                        side=side,
                        entry_idx=widen_idx,
                        exit_idx=widen_exit,
                        reason=(
                            f"cascade_widen side={side} ask={widen_ask:.3f} "
                            f"delta={delta[widen_idx]:.4%} stop={widen_stop:.3f}"
                        ),
                    )
                )

        # --- Tranche 3: add at T-60s if token still discounted vs fair --------
        add3_idx = int(np.argmin(np.abs(rem - p["t_add_60"])))
        if add3_idx > (signals[-1].entry_idx if signals else probe_idx):
            if not prior_stop_hit(add3_idx):
                add3_ask = float(ask_arr[add3_idx])
                if (
                    not (np.isnan(add3_ask) or add3_ask <= 0 or add3_ask > p["max_price"])
                    and side_sign * delta[add3_idx] > 0
                    and add3_ask <= fair - p["fair_discount_cents"]
                ):
                    add3_stop = add3_ask - p["stop_cents"]
                    add3_exit = self._find_stop_exit(market, add3_idx, side, add3_stop)
                    signals.append(
                        Signal(
                            side=side,
                            entry_idx=add3_idx,
                            exit_idx=add3_exit,
                            reason=(
                                f"cascade_t60 side={side} ask={add3_ask:.3f} "
                                f"delta={delta[add3_idx]:.4%} stop={add3_stop:.3f}"
                            ),
                        )
                    )

        # --- Tranche 4: final add at T-15s if delta still agrees --------------
        add4_idx = int(np.argmin(np.abs(rem - p["t_add_15"])))
        if add4_idx > (signals[-1].entry_idx if signals else probe_idx):
            if not prior_stop_hit(add4_idx):
                add4_ask = float(ask_arr[add4_idx])
                if (
                    not (np.isnan(add4_ask) or add4_ask <= 0 or add4_ask > p["max_price"])
                    and side_sign * delta[add4_idx] > 0
                ):
                    add4_stop = add4_ask - p["stop_cents"]
                    add4_exit = self._find_stop_exit(market, add4_idx, side, add4_stop)
                    signals.append(
                        Signal(
                            side=side,
                            entry_idx=add4_idx,
                            exit_idx=add4_exit,
                            reason=(
                                f"cascade_t15 side={side} ask={add4_ask:.3f} "
                                f"delta={delta[add4_idx]:.4%} stop={add4_stop:.3f}"
                            ),
                        )
                    )

        return signals

    def _find_stop_exit(
        self, market: Market, entry_idx: int, side: str, stop_price: float
    ) -> Optional[int]:
        """Return first index after entry where bid <= stop_price, else None."""
        n = len(market)
        bid_arr = market.best_bid_up if side == "YES" else market.best_bid_down
        for idx in range(entry_idx + 1, n):
            bid = float(bid_arr[idx])
            if not np.isnan(bid) and bid <= stop_price:
                return idx
        return None

    def param_sweep(self):
        for ed in [0.0008, 0.001, 0.0015]:
            for tp in [120.0, 150.0, 180.0]:
                for wr in [0.4, 0.5, 0.6]:
                    for sc in [0.06, 0.08, 0.10]:
                        yield {
                            "entry_delta": ed,
                            "t_probe": tp,
                            "widen_ratio": wr,
                            "t_add_60": 60.0,
                            "t_add_15": 15.0,
                            "stop_cents": sc,
                            "fair_discount_cents": 0.04,
                            "max_price": 0.70,
                        }, f"ed{ed}_tp{tp}_wr{wr}_sc{sc}"
