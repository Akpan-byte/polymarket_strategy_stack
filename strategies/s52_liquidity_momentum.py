"""Strategy 52: Liquidity Momentum (Order-Book Influence + Spot-Strike Confirmation).
Proxies an order-book "influence" score from changes in the top-of-book quotes
and token price, confirms the direction with spot-vs-strike delta, and exits
when the influence decays or a hard time stop is reached.
"""
import math
import numpy as np
from typing import List, Optional

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


def _norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


class S52LiquidityMomentum(Strategy):
    name = "S52_Liquidity_Momentum"

    def __init__(
        self,
        infl_window: int = 10,
        percentile: float = 0.95,
        min_delta: float = 0.0001,
        max_price: float = 0.70,
        max_hold_ticks: int = 120,
    ):
        self.params = {
            "infl_window": infl_window,
            "percentile": percentile,
            "min_delta": min_delta,
            "max_price": max_price,
            "max_hold_ticks": max_hold_ticks,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        w = p["infl_window"]
        if n < w + 5:
            return []

        # Proxy influence from top-of-book migration and token-price velocity.
        # Signed pressure: bid rising and ask being lifted = positive for UP;
        # the mirror holds for DOWN.  Large single-tick moves get sweep weight.
        infl_up = np.zeros(n)
        infl_down = np.zeros(n)
        for i in range(1, n):
            bid_up_chg = market.best_bid_up[i] - market.best_bid_up[i - 1]
            ask_up_chg = market.best_ask_up[i] - market.best_ask_up[i - 1]
            price_up_chg = market.price_up[i] - market.price_up[i - 1]
            sweep_weight = 2.0 if abs(price_up_chg) >= 0.015 else 1.0
            infl_up[i] = (bid_up_chg - ask_up_chg + price_up_chg) * sweep_weight

            bid_down_chg = market.best_bid_down[i] - market.best_bid_down[i - 1]
            ask_down_chg = market.best_ask_down[i] - market.best_ask_down[i - 1]
            price_down_chg = market.price_down[i] - market.price_down[i - 1]
            sweep_weight = 2.0 if abs(price_down_chg) >= 0.015 else 1.0
            infl_down[i] = (bid_down_chg - ask_down_chg + price_down_chg) * sweep_weight

        for idx in range(w, n - p["max_hold_ticks"] - 1):
            d = market.delta_pct[idx]
            if abs(d) < p["min_delta"]:
                continue
            side = "YES" if d > 0 else "NO"

            ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
            if np.isnan(ask) or ask <= 0 or ask > p["max_price"]:
                continue

            infl = infl_up if side == "YES" else infl_down
            window_infl = float(np.sum(infl[idx - w + 1:idx + 1]))

            # Confirm direction: influence and spot delta agree.
            if np.sign(window_infl) != np.sign(d):
                continue
            if abs(window_infl) < 1e-9:
                continue

            # Trigger when influence exceeds the running percentile within this market.
            hist = infl[:idx + 1]
            if len(hist) < w:
                continue
            threshold = float(np.percentile(np.abs(hist), p["percentile"] * 100))
            if threshold <= 1e-9:
                threshold = 0.01
            if abs(window_infl) < threshold:
                continue

            exit_idx = self._find_exit(market, idx, side, infl, p)
            reason = (
                f"liquidity_momentum side={side} infl={window_infl:.4f} "
                f"thr={threshold:.4f} ask={ask:.3f} delta={d:.4%}"
            )
            return [Signal(side=side, entry_idx=idx, exit_idx=exit_idx, reason=reason)]

        return []

    def _find_exit(
        self,
        market: Market,
        entry_idx: int,
        side: str,
        infl: np.ndarray,
        p: dict,
    ) -> Optional[int]:
        n = len(market)
        w = p["infl_window"]
        max_j = min(n - 1, entry_idx + p["max_hold_ticks"])

        for j in range(entry_idx + 1, max_j + 1):
            if market.rem_sec[j] < 1.0:
                return j

            # Early exit when influence has fully decayed to zero.
            recent_infl = float(np.sum(infl[j - w + 1:j + 1])) if j >= w else float(infl[j])
            if abs(recent_infl) < 1e-9:
                return j

        return max_j

    def param_sweep(self):
        for iw in [5, 10, 15]:
            for pct in [0.90, 0.95]:
                for md in [0.0001, 0.0002]:
                    for mp in [0.60, 0.70, 0.80]:
                        for mht in [80, 120]:
                            yield {
                                "infl_window": iw,
                                "percentile": pct,
                                "min_delta": md,
                                "max_price": mp,
                                "max_hold_ticks": mht,
                            }, f"iw{iw}_pct{pct}_md{md}_mp{mp}_mht{mht}"
