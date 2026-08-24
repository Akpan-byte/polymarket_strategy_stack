"""Strategy 25: Last-Second Momentum Snipe with Partial Hedge (80/20).
Buy the leading token when spot momentum is up but the token still trades
below 0.48. The hedge is proxied by requiring the opposite token to retain
residual value (ask >= hedge_min).
"""
import numpy as np
from typing import List
from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S25MomentumSnipeHedge(Strategy):
    name = "S25_MomentumSnipe_Hedge"

    def __init__(self, ret_1m_min: float = 0.001, max_price: float = 0.48,
                 hedge_min: float = 0.10, t_entry: float = 90.0,
                 t_min: float = 10.0):
        self.params = {
            "ret_1m_min": ret_1m_min,
            "max_price": max_price,
            "hedge_min": hedge_min,
            "t_entry": t_entry,
            "t_min": t_min,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        if n < 10:
            return []

        mask = (market.rem_sec <= p["t_entry"]) & (market.rem_sec >= p["t_min"])
        idxs = np.where(mask)[0]
        if idxs.size == 0:
            return []
        idx = int(idxs[0])

        # 1-minute spot return
        t0 = max(0, int(np.searchsorted(market.ts, market.ts[idx] - 60.0, side="left")))
        if t0 == idx:
            return []
        ret_1m = (market.spot[idx] - market.spot[t0]) / market.spot[t0]
        if abs(ret_1m) < p["ret_1m_min"]:
            return []
        side = "YES" if ret_1m > 0 else "NO"

        # Token still cheap
        ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
        if np.isnan(ask) or ask > p["max_price"]:
            return []

        # Spot and token direction align
        d = market.delta_pct[idx]
        if np.sign(d) != np.sign(ret_1m):
            return []

        # Hedge proxy: opposite token retains residual value
        opp = "NO" if side == "YES" else "YES"
        opp_ask = market.best_ask_down[idx] if opp == "NO" else market.best_ask_up[idx]
        if np.isnan(opp_ask) or opp_ask < p["hedge_min"]:
            return []

        return [Signal(side=side, entry_idx=idx,
                       reason=f"mom_snipe ret={ret_1m:.4%} ask={ask:.3f} hedge_opp={opp_ask:.3f}")]

    def param_sweep(self):
        for r in [0.0008, 0.001, 0.0015]:
            for mp in [0.42, 0.48, 0.55]:
                for hm in [0.05, 0.10, 0.15]:
                    for te in [60, 90, 120]:
                        yield {
                            "ret_1m_min": r,
                            "max_price": mp,
                            "hedge_min": hm,
                            "t_entry": te,
                            "t_min": 10.0,
                        }, f"r{r}_mp{mp}_hm{hm}_te{te}"
