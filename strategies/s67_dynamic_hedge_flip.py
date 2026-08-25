"""Strategy 67: Dynamic Hedge-Flip on Loss Signals.

Enter a directional position once a minimum delta has developed, then monitor
for an adverse move that is accompanied by a velocity spike. When both hit,
exit the initial position and flip to the opposite side. If the original
direction later reclaims part of the loss, unwind the hedge. One flip per
market window.
"""
import numpy as np
from typing import List

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S67DynamicHedgeFlip(Strategy):
    name = "S67_Dynamic_Hedge_Flip"

    def __init__(
        self,
        entry_delay_sec: float = 60.0,
        min_delta: float = 0.0005,
        adverse_pct: float = 0.01,
        vel_window: int = 5,
        volume_mult: float = 2.0,
        reclaim_frac: float = 0.5,
        max_price: float = 0.70,
    ):
        self.params = {
            "entry_delay_sec": entry_delay_sec,
            "min_delta": min_delta,
            "adverse_pct": adverse_pct,
            "vel_window": vel_window,
            "volume_mult": volume_mult,
            "reclaim_frac": reclaim_frac,
            "max_price": max_price,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        min_required = max(p["vel_window"] * 3, 10)
        if n < min_required + 5:
            return []

        # Side-specific book columns
        ask_of = {"YES": market.best_ask_up, "NO": market.best_ask_down}
        bid_of = {"YES": market.best_bid_up, "NO": market.best_bid_down}

        # Absolute velocity of delta_pct (per second)
        vel = np.full(n, np.nan)
        vw = p["vel_window"]
        dt = np.maximum(
            market.elapsed_sec[vw:] - market.elapsed_sec[:-vw],
            1e-9,
        )
        vel[vw:] = np.abs((market.delta_pct[vw:] - market.delta_pct[:-vw]) / dt)

        # Baseline = rolling median absolute velocity over the prior window.
        baseline = np.full(n, np.nan)
        for i in range(2 * vw, n):
            baseline[i] = np.nanmedian(vel[i - vw : i])

        signals: List[Signal] = []
        i = 0
        while i < n - 10:
            if market.elapsed_sec[i] < p["entry_delay_sec"]:
                i += 1
                continue

            d = market.delta_pct[i]
            if abs(d) < p["min_delta"]:
                i += 1
                continue

            side = "YES" if d > 0 else "NO"
            entry_ask = ask_of[side][i]
            if (
                np.isnan(entry_ask)
                or entry_ask <= 0
                or entry_ask >= 1.0
                or entry_ask > p["max_price"]
            ):
                i += 1
                continue

            entry_price = float(entry_ask)
            flip_side = "NO" if side == "YES" else "YES"
            flip_idx = -1
            flip_price = np.nan
            adverse_at_flip = 0.0

            for j in range(i + 1, n):
                current_bid = bid_of[side][j]
                if not np.isnan(current_bid) and entry_price > 0:
                    adverse = abs(entry_price - current_bid) / entry_price
                else:
                    adverse = 0.0

                v = vel[j]
                b = baseline[j]
                if (
                    adverse >= p["adverse_pct"]
                    and not np.isnan(v)
                    and not np.isnan(b)
                    and v >= p["volume_mult"] * b
                ):
                    opp_ask = ask_of[flip_side][j]
                    if not np.isnan(opp_ask) and 0 < opp_ask < 1.0 and opp_ask <= p["max_price"]:
                        flip_idx = j
                        flip_price = float(opp_ask)
                        adverse_at_flip = adverse
                        break

            if flip_idx == -1:
                # Hold the directional bet to resolution; no flip this window.
                signals.append(
                    Signal(
                        side=side,
                        entry_idx=i,
                        exit_idx=None,
                        reason=f"delta={d:.4%} at T-{market.rem_sec[i]:.1f}s (no flip)",
                    )
                )
                break

            # Compute the reclaim target on the original-side price.
            flip_bid = bid_of[side][flip_idx]
            if np.isnan(flip_bid):
                # Fallback estimate from the adverse threshold.
                if side == "YES":
                    flip_bid = entry_price * (1.0 - p["adverse_pct"])
                else:
                    flip_bid = entry_price * (1.0 + p["adverse_pct"])

            if side == "YES":
                distance = entry_price - flip_bid
                unwind_target = flip_bid + p["reclaim_frac"] * distance
            else:
                distance = flip_bid - entry_price
                unwind_target = flip_bid - p["reclaim_frac"] * distance

            unwind_idx = -1
            for k in range(flip_idx + 1, n):
                cur_bid = bid_of[side][k]
                if np.isnan(cur_bid):
                    continue
                if (side == "YES" and cur_bid >= unwind_target) or (
                    side == "NO" and cur_bid <= unwind_target
                ):
                    unwind_idx = k
                    break

            signals.append(
                Signal(
                    side=side,
                    entry_idx=i,
                    exit_idx=flip_idx,
                    reason=(
                        f"delta={d:.4%} entry T-{market.rem_sec[i]:.1f}s "
                        f"flip@{flip_idx}"
                    ),
                )
            )
            signals.append(
                Signal(
                    side=flip_side,
                    entry_idx=flip_idx,
                    exit_idx=unwind_idx if unwind_idx != -1 else None,
                    reason=(
                        f"hedge-flip {flip_side} adverse={adverse_at_flip:.2%} "
                        f"vel={vel[flip_idx]:.4f}"
                    ),
                )
            )
            # One flip per window.
            break

        return signals

    def param_sweep(self):
        for eds in [30.0, 60.0]:
            for md in [0.0003, 0.0005, 0.001]:
                for ap in [0.005, 0.01]:
                    for vm in [1.5, 2.5]:
                        for vw in [5, 10]:
                            for rf in [0.5, 0.75]:
                                yield {
                                    "entry_delay_sec": eds,
                                    "min_delta": md,
                                    "adverse_pct": ap,
                                    "vel_window": vw,
                                    "volume_mult": vm,
                                    "reclaim_frac": rf,
                                    "max_price": 0.70,
                                }, (
                                    f"eds{eds}_md{md}_ap{ap}_"
                                    f"vm{vm}_vw{vw}_rf{rf}"
                                )
