"""Strategy 58: Post-Release Drift Continuation.
After a decisive post-release move, wait for a pullback to hold, then enter
in the drift direction while the token is still cheap.
"""
import numpy as np
from typing import List

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S58PostReleaseDriftContinuation(Strategy):
    name = "S58_Post_Release_Drift_Continuation"

    def __init__(
        self,
        release_window_sec: float = 60.0,
        decisive_move_pct: float = 0.004,
        pullback_retrace_pct: float = 0.25,
        pullback_hold_sec: float = 120.0,
        max_entry_price: float = 0.55,
        max_trades: int = 3,
        no_trade_after_sec: float = 3600.0,
        stop_if_reverses: bool = True,
    ):
        self.params = {
            "release_window_sec": release_window_sec,
            "decisive_move_pct": decisive_move_pct,
            "pullback_retrace_pct": pullback_retrace_pct,
            "pullback_hold_sec": pullback_hold_sec,
            "max_entry_price": max_entry_price,
            "max_trades": max_trades,
            "no_trade_after_sec": no_trade_after_sec,
            "stop_if_reverses": stop_if_reverses,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        if n < 10:
            return []

        release_mask = market.elapsed_sec <= p["release_window_sec"]
        release_idxs = np.where(release_mask)[0]
        if release_idxs.size == 0:
            return []

        release_deltas = market.delta_pct[release_idxs]
        if np.all(np.isnan(release_deltas)):
            return []

        max_delta = float(np.nanmax(release_deltas))
        min_delta = float(np.nanmin(release_deltas))
        decisive = p["decisive_move_pct"]

        # Choose the stronger directional move if both directions triggered.
        up_ok = max_delta >= decisive
        down_ok = min_delta <= -decisive
        if up_ok and down_ok:
            if max_delta >= abs(min_delta):
                side = "YES"
                decisive_delta = max_delta
            else:
                side = "NO"
                decisive_delta = min_delta
        elif up_ok:
            side = "YES"
            decisive_delta = max_delta
        elif down_ok:
            side = "NO"
            decisive_delta = min_delta
        else:
            return []

        strike = market.strike
        decisive_level = strike * (1.0 + decisive_delta)
        retrace = p["pullback_retrace_pct"]
        if side == "YES":
            pullback_level = decisive_level - retrace * (decisive_level - strike)
        else:
            pullback_level = decisive_level + retrace * (strike - decisive_level)

        signals: List[Signal] = []
        trades = 0
        in_pullback = False
        pullback_start_idx = -1
        hold_met = False
        last_entry_idx = -1

        scan_start = int(release_idxs[-1]) + 1
        for idx in range(scan_start, n - 1):
            if market.elapsed_sec[idx] >= p["no_trade_after_sec"]:
                break

            spot = market.spot[idx]
            delta = market.delta_pct[idx]
            if np.isnan(spot) or np.isnan(delta):
                continue

            # Window resolves against the drift if spot crosses strike.
            if p["stop_if_reverses"]:
                if side == "YES" and delta < 0:
                    break
                if side == "NO" and delta > 0:
                    break

            if side == "YES":
                if not in_pullback and spot <= pullback_level:
                    in_pullback = True
                    pullback_start_idx = idx
                    hold_met = False
                elif in_pullback:
                    if spot < pullback_level:
                        # broke support, reset
                        in_pullback = False
                        hold_met = False
                    elif (
                        market.elapsed_sec[idx] - market.elapsed_sec[pullback_start_idx]
                        >= p["pullback_hold_sec"]
                    ):
                        hold_met = True
            else:
                if not in_pullback and spot >= pullback_level:
                    in_pullback = True
                    pullback_start_idx = idx
                    hold_met = False
                elif in_pullback:
                    if spot > pullback_level:
                        # broke resistance, reset
                        in_pullback = False
                        hold_met = False
                    elif (
                        market.elapsed_sec[idx] - market.elapsed_sec[pullback_start_idx]
                        >= p["pullback_hold_sec"]
                    ):
                        hold_met = True

            if (
                hold_met
                and trades < p["max_trades"]
                and idx != last_entry_idx
            ):
                ask = (
                    market.best_ask_up[idx]
                    if side == "YES"
                    else market.best_ask_down[idx]
                )
                if not np.isnan(ask) and ask <= p["max_entry_price"]:
                    signals.append(
                        Signal(
                            side=side,
                            entry_idx=idx,
                            reason=(
                                f"post_release_drift side={side} ask={ask:.3f} "
                                f"decisive={decisive_delta:.4%} "
                                f"pull_level={pullback_level:.2f}"
                            ),
                        )
                    )
                    trades += 1
                    last_entry_idx = idx
                    # Require a fresh pullback for the next drift entry.
                    in_pullback = False
                    hold_met = False

        return signals

    def param_sweep(self):
        for rw in [30.0, 60.0]:
            for dm in [0.003, 0.004, 0.005]:
                for pr in [0.20, 0.25]:
                    for ph in [60.0, 120.0]:
                        for mp in [0.50, 0.55]:
                            yield {
                                "release_window_sec": rw,
                                "decisive_move_pct": dm,
                                "pullback_retrace_pct": pr,
                                "pullback_hold_sec": ph,
                                "max_entry_price": mp,
                                "max_trades": 3,
                                "no_trade_after_sec": 3600.0,
                                "stop_if_reverses": True,
                            }, f"rw{rw}_dm{dm}_pr{pr}_ph{ph}_mp{mp}"
