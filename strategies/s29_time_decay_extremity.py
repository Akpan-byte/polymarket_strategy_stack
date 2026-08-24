"""Strategy 29: Time-Decay Extremity Entry.
In the final seconds, buy the cheap side when time decay has pushed its ask
to an extreme low, but the spot has not moved so far that the outcome is a
foregone conclusion.
"""
import numpy as np
from typing import List
from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S29TimeDecayExtremity(Strategy):
    name = "S29_TimeDecay_Extremity"

    def __init__(self, t_entry: float = 10.0, t_min: float = 1.0,
                 ask_max: float = 0.20, delta_buffer: float = 0.0002,
                 twap_window: int = 20):
        self.params = {
            "t_entry": t_entry,
            "t_min": t_min,
            "ask_max": ask_max,
            "delta_buffer": delta_buffer,
            "twap_window": twap_window,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        mask = (market.rem_sec <= p["t_entry"]) & (market.rem_sec >= p["t_min"])
        idxs = np.where(mask)[0]
        if idxs.size == 0:
            return []

        idx = int(idxs[0])
        d = market.delta_pct[idx]

        # Pick the cheaper token (higher implied payout if it wins)
        ask_up = market.best_ask_up[idx]
        ask_down = market.best_ask_down[idx]
        if np.isnan(ask_up) or np.isnan(ask_down):
            return []

        if ask_up <= ask_down:
            side, ask = "YES", ask_up
        else:
            side, ask = "NO", ask_down

        if ask > p["ask_max"]:
            return []

        # Do not buy the side that spot strongly disagrees with
        if side == "YES" and d < -p["delta_buffer"]:
            return []
        if side == "NO" and d > p["delta_buffer"]:
            return []

        # Confirm with short TWAP that spot is not violently against the trade
        t0 = max(0, idx - p["twap_window"])
        twap = float(np.mean(market.spot[t0:idx + 1]))
        twap_d = (twap - market.strike) / market.strike
        if side == "YES" and twap_d < -p["delta_buffer"]:
            return []
        if side == "NO" and twap_d > p["delta_buffer"]:
            return []

        return [Signal(side=side, entry_idx=idx,
                       reason=f"extremity ask={ask:.3f} side={side} delta={d:.4%} T-{market.rem_sec[idx]:.1f}s")]

    def param_sweep(self):
        for te in [5, 10, 15]:
            for tm in [0.5, 1.0, 2.0]:
                for am in [0.12, 0.18, 0.25]:
                    for db in [0.0001, 0.0002, 0.0003]:
                        yield {
                            "t_entry": te,
                            "t_min": tm,
                            "ask_max": am,
                            "delta_buffer": db,
                            "twap_window": 20,
                        }, f"te{te}_tm{tm}_am{am}_db{db}"
