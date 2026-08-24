"""Strategy 41: Post-Shakeout Confirmed Reversal (Thuroff 5-Minute Rule).
No entry in first 5 minutes; enter after minute 5 when direction held >=60s and token is mispriced.
"""
import numpy as np
from typing import List
from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S41PostShakeoutReversal(Strategy):
    name = "S41_PostShakeout_Reversal"

    def __init__(self, no_trade_sec: float = 300.0, hold_sec: float = 60.0,
                 gap_min: float = 0.15, min_rv_1h: float = 0.003):
        self.params = {
            "no_trade_sec": no_trade_sec,
            "hold_sec": hold_sec,
            "gap_min": gap_min,
            "min_rv_1h": min_rv_1h,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        if n < 10:
            return []

        # Candidate index after no-trade period
        idx = int(np.searchsorted(market.elapsed_sec, p["no_trade_sec"], side="left"))
        if idx >= n - 5:
            return []

        # Direction held for hold_sec
        t0 = max(0, int(np.searchsorted(market.elapsed_sec, market.elapsed_sec[idx] - p["hold_sec"], side="left")))
        d = market.delta_pct[idx]
        if abs(d) < 1e-9:
            return []
        side = "YES" if d > 0 else "NO"
        if np.sign(market.delta_pct[t0:idx+1]).mean() < 0.8:
            return []

        # Mispricing: token ask is far below what delta implies (crude gap)
        ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
        if np.isnan(ask):
            return []
        # Use absolute delta as rough proxy for fair value
        fair = min(0.95, 0.5 + abs(d) * 1000)  # heuristic mapping
        if fair - ask < p["gap_min"]:
            return []

        # Volatility filter: require some hourly movement in the spot series
        rets = np.diff(market.spot[max(0, idx-60):idx+1]) / market.spot[max(0, idx-60):idx]
        rv = float(np.std(rets)) if len(rets) > 1 else 0
        if rv < p["min_rv_1h"]:
            return []

        return [Signal(side=side, entry_idx=idx, reason=f"post-shakeout fair={fair:.2f} ask={ask:.2f}")]

    def param_sweep(self):
        for nts in [240, 300, 360]:
            for hs in [30, 60, 90]:
                for gm in [0.10, 0.15, 0.20]:
                    for mrv in [0.002, 0.003, 0.004]:
                        yield {
                            "no_trade_sec": nts,
                            "hold_sec": hs,
                            "gap_min": gm,
                            "min_rv_1h": mrv,
                        }, f"nts{nts}_hs{hs}_gm{gm}_mrv{mrv}"
