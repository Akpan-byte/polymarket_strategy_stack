"""Strategy 63: LLM-Filtered Composite with Mechanical Trend Veto.

Cheap directional entry filtered by a 10-minute mechanical trend veto.
"""
import numpy as np
from typing import List

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S63LlmFilteredTrendVeto(Strategy):
    name = "S63_LLM_Filtered_Trend_Veto"

    def __init__(
        self,
        t_entry: float = 30.0,
        momentum_window_sec: float = 60.0,
        trend_window_sec: float = 600.0,
        delta_min: float = 0.0001,
        momentum_weight: float = 1.0,
        trend_threshold: float = 0.0002,
    ):
        self.params = {
            "t_entry": t_entry,
            "momentum_window_sec": momentum_window_sec,
            "trend_window_sec": trend_window_sec,
            "delta_min": delta_min,
            "momentum_weight": momentum_weight,
            "trend_threshold": trend_threshold,
        }

    def _idx_at(self, market: Market, target_elapsed: float, end_idx: int) -> int:
        """Return the index nearest to target_elapsed seconds before end_idx."""
        target = market.elapsed_sec[end_idx] - target_elapsed
        if target <= 0:
            return -1
        return int(np.argmin(np.abs(market.elapsed_sec[:end_idx] - target)))

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        if n < 10:
            return []

        # Entry near T - t_entry seconds remaining.
        idx = int(np.argmin(np.abs(market.rem_sec - p["t_entry"])))
        if market.rem_sec[idx] < 3 or market.rem_sec[idx] > 90:
            return []

        delta = market.delta_pct[idx]
        if abs(delta) < p["delta_min"]:
            return []

        # Momentum: change in delta_pct over the last momentum_window_sec.
        mom_idx = self._idx_at(market, p["momentum_window_sec"], idx)
        if mom_idx < 0 or mom_idx >= idx:
            momentum = 0.0
        else:
            momentum = market.delta_pct[idx] - market.delta_pct[mom_idx]

        # Composite directional score.
        score = delta + p["momentum_weight"] * momentum
        if abs(score) < p["delta_min"]:
            return []
        side = "YES" if score > 0 else "NO"

        # 10-minute trend filter.
        trend_idx = self._idx_at(market, p["trend_window_sec"], idx)
        if trend_idx >= 0 and trend_idx < idx:
            trend = (market.spot[idx] - market.spot[trend_idx]) / market.spot[trend_idx]
        else:
            trend = 0.0

        trend_side = np.sign(trend)
        score_side = np.sign(score)
        if abs(trend) >= p["trend_threshold"] and trend_side != 0 and trend_side != score_side:
            return []

        # Ensure a fillable ask on the chosen side.
        ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
        if np.isnan(ask) or ask <= 0 or ask >= 1.0:
            return []

        reason = (
            f"delta={delta:.4%} mom={momentum:.4%} "
            f"trend={trend:.4%} side={side} at T-{market.rem_sec[idx]:.1f}s"
        )
        return [Signal(side=side, entry_idx=idx, reason=reason)]

    def param_sweep(self):
        for t in [5, 10, 15]:
            for dm in [0.00005, 0.0001, 0.0002]:
                for mwgt in [0.5, 1.0, 1.5]:
                    for th in [0.0001, 0.0002, 0.0003]:
                        yield {
                            "t_entry": t,
                            "momentum_window_sec": 60.0,
                            "trend_window_sec": 600.0,
                            "delta_min": dm,
                            "momentum_weight": mwgt,
                            "trend_threshold": th,
                        }, f"t{t}_dm{dm}_mwgt{mwgt}_th{th}"
