"""Strategy 69: Complementary-Exit Discipline.
Enter a directional position and continuously recompute a model probability of
winning.  Exit when the model probability decays to less than half of the entry
model probability while the token still has residual value (bid >= 0.08).
"""
import math
import numpy as np
from typing import List, Optional

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


def _norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _model_prob(market: Market, idx: int, side: str, vol_window: int = 60) -> float:
    """Simple binary fair-value proxy using spot delta and realized vol."""
    spot = market.spot[idx]
    strike = market.strike
    delta = spot - strike
    t0 = max(0, idx - vol_window)
    rets = np.diff(market.spot[t0:idx + 1]) / market.spot[t0:idx]
    sigma = float(np.std(rets)) if len(rets) > 1 else 0.001
    if sigma <= 1e-9:
        sigma = 0.001
    t_rem = max(market.rem_sec[idx], 1.0) / 300.0
    p_yes = _norm_cdf(delta / strike / (sigma * math.sqrt(t_rem)))
    return p_yes if side == "YES" else 1.0 - p_yes


class S69ComplementaryExitDiscipline(Strategy):
    name = "S69_Complementary_ExitDiscipline"

    def __init__(
        self,
        trend_window: int = 5,
        min_delta: float = 0.0002,
        max_price: float = 0.70,
        decay_factor: float = 0.5,
        residual_floor: float = 0.08,
        max_hold_ticks: int = 120,
    ):
        self.params = {
            "trend_window": trend_window,
            "min_delta": min_delta,
            "max_price": max_price,
            "decay_factor": decay_factor,
            "residual_floor": residual_floor,
            "max_hold_ticks": max_hold_ticks,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        tw = p["trend_window"]
        if n < tw + 5:
            return []

        for idx in range(tw, n - p["max_hold_ticks"] - 1):
            d = market.delta_pct[idx]
            if abs(d) < p["min_delta"]:
                continue
            side = "YES" if d > 0 else "NO"

            prices = market.price_up if side == "YES" else market.price_down
            if np.isnan(prices[idx]) or np.isnan(prices[idx - tw]):
                continue
            trend = float(prices[idx] - prices[idx - tw])
            if np.sign(trend) != (np.sign(d) if side == 'YES' else -np.sign(d)):
                continue

            ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
            if np.isnan(ask) or ask <= 0 or ask > p["max_price"]:
                continue

            entry_prob = _model_prob(market, idx, side)
            exit_idx = self._find_exit(market, idx, side, ask, entry_prob, p)
            reason = (
                f"comp_exit_discipline side={side} ask={ask:.3f} "
                f"p_entry={entry_prob:.3f} delta={d:.4%}"
            )
            return [Signal(side=side, entry_idx=idx, exit_idx=exit_idx, reason=reason)]

        return []

    def _find_exit(
        self,
        market: Market,
        entry_idx: int,
        side: str,
        entry_price: float,
        entry_prob: float,
        p: dict,
    ) -> Optional[int]:
        n = len(market)
        max_j = min(n - 1, entry_idx + p["max_hold_ticks"])
        best_bid = market.best_bid_up if side == "YES" else market.best_bid_down

        for j in range(entry_idx + 1, max_j + 1):
            if market.rem_sec[j] < 1.0:
                return j

            bid = best_bid[j]
            if np.isnan(bid):
                continue

            # Never sell below the residual floor: hold to resolution as a lottery ticket.
            if bid < p["residual_floor"]:
                continue

            # Decay trigger: model P(win) has fallen below decay_factor * entry P.
            p_now = _model_prob(market, j, side)
            if p_now < p["decay_factor"] * entry_prob:
                return j

        return max_j

    def param_sweep(self):
        for tw in [4, 5, 6]:
            for md in [0.0001, 0.0002]:
                for mp in [0.60, 0.70, 0.80]:
                    for df in [0.40, 0.60]:
                        for rf in [0.06, 0.10]:
                            for mht in [80, 120]:
                                yield {
                                    "trend_window": tw,
                                    "min_delta": md,
                                    "max_price": mp,
                                    "decay_factor": df,
                                    "residual_floor": rf,
                                    "max_hold_ticks": mht,
                                }, f"tw{tw}_md{md}_mp{mp}_df{df}_rf{rf}_mht{mht}"
