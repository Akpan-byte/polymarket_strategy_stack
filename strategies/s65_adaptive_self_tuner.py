"""Strategy 65: Adaptive Self-Tuner.
Wrap a late-window delta entry and adapt the entry threshold based on a rolling
win-rate score versus an expected baseline.  The strategy keeps an internal
history of completed (simulated) trades and becomes more selective after
underperformance and more permissive after outperformance.
"""
import numpy as np
from typing import List

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S65AdaptiveSelfTuner(Strategy):
    name = "S65_Adaptive_Self_Tuner"

    def __init__(
        self,
        t_entry: float = 10.0,
        delta_min: float = 0.0002,
        max_price: float = 0.70,
        wr_window: int = 20,
        expected_wr: float = 0.50,
        loosen_pts: float = 0.05,
        tighten_pts: float = 0.05,
        suspend_pts: float = 0.10,
        loosen_mult: float = 0.75,
        tighten_mult: float = 1.5,
    ):
        self.params = {
            "t_entry": t_entry,
            "delta_min": delta_min,
            "max_price": max_price,
            "wr_window": wr_window,
            "expected_wr": expected_wr,
            "loosen_pts": loosen_pts,
            "tighten_pts": tighten_pts,
            "suspend_pts": suspend_pts,
            "loosen_mult": loosen_mult,
            "tighten_mult": tighten_mult,
        }
        # Stateful win-rate tracker updated after each market that produces a
        # signal.  The current entry decision only uses history from prior
        # markets, so the signal itself is not look-ahead.
        self._history: List[int] = []

    def _threshold_factor(self) -> float:
        """Return multiplier for delta_min based on rolling win rate.

        Factor > 1.0 tightens (raises threshold), factor < 1.0 loosens (lowers
        threshold), and factor == 0.0 suspends entries.
        """
        p = self.params
        hist = self._history
        w = p["wr_window"]
        # Require at least half the window before adapting.
        if len(hist) < max(1, w // 2):
            return 1.0
        rolling_wr = float(np.mean(hist[-w:]))
        diff = rolling_wr - p["expected_wr"]
        if diff >= p["loosen_pts"]:
            return p["loosen_mult"]
        if diff <= -p["suspend_pts"]:
            return 0.0
        if diff <= -p["tighten_pts"]:
            return p["tighten_mult"]
        return 1.0

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        rem = market.rem_sec
        idx = int(np.argmin(np.abs(rem - p["t_entry"])))
        if rem[idx] < 3 or rem[idx] > 30:
            return []

        factor = self._threshold_factor()
        if factor <= 0.0:
            return []

        d = market.delta_pct[idx]
        ad = abs(d)
        threshold = p["delta_min"] * factor
        if ad < threshold:
            return []

        side = "YES" if d > 0 else "NO"
        ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
        if np.isnan(ask) or ask <= 0 or ask > p["max_price"]:
            return []

        sig = Signal(
            side=side,
            entry_idx=idx,
            reason=(
                f"adaptive_self_tuner side={side} delta={d:.4%} "
                f"threshold={threshold:.4%} T-{rem[idx]:.1f}s factor={factor:.2f}"
            ),
        )

        # Record the simulated outcome for future markets.  Resolution is used
        # here, but only after the current entry decision has been made.
        win = 1 if market.resolution == sig.side else 0
        self._history.append(win)
        if len(self._history) > max(50, self.params["wr_window"] * 2):
            self._history.pop(0)

        return [sig]

    def param_sweep(self):
        for te in [5.0, 10.0, 15.0]:
            for dm in [0.0001, 0.0002, 0.0003]:
                for ww in [10, 20, 30]:
                    for mp in [0.60, 0.70]:
                        yield {
                            "t_entry": te,
                            "delta_min": dm,
                            "max_price": mp,
                            "wr_window": ww,
                            "expected_wr": 0.50,
                            "loosen_pts": 0.05,
                            "tighten_pts": 0.05,
                            "suspend_pts": 0.10,
                            "loosen_mult": 0.75,
                            "tighten_mult": 1.5,
                        }, f"te{te}_dm{dm}_ww{ww}_mp{mp}"
