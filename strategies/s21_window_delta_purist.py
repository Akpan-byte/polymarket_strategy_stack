"""Strategy 21: Single-Signal Window-Delta Purist.
Entry at T-10s based solely on window delta magnitude.
"""
import numpy as np
from typing import List
from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S21WindowDeltaPurist(Strategy):
    name = "S21_WindowDelta_Purist"

    def __init__(self, t_entry: float = 10.0, delta_full: float = 0.001,
                 delta_half: float = 0.0002, delta_min: float = 0.00005,
                 use_oracle_veto: bool = False):
        self.params = {
            "t_entry": t_entry,
            "delta_full": delta_full,
            "delta_half": delta_half,
            "delta_min": delta_min,
            "use_oracle_veto": use_oracle_veto,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        # Find snapshot closest to T-10s remaining
        rem = market.rem_sec
        idx = int(np.argmin(np.abs(rem - p["t_entry"])))
        if rem[idx] < 3 or rem[idx] > 30:
            return []
        d = market.delta_pct[idx]
        ad = abs(d)
        if ad < p["delta_min"]:
            return []
        side = "YES" if d > 0 else "NO"
        if p["use_oracle_veto"]:
            # Simple oracle-veto stub: require spot and delta agree with leading side
            pass
        reason = f"delta={d:.4%} at T-{rem[idx]:.1f}s"
        return [Signal(side=side, entry_idx=idx, reason=reason)]

    def param_sweep(self):
        for t in [5, 10, 15, 20]:
            for df in [0.0008, 0.001, 0.0015]:
                for dh in [0.00015, 0.0002, 0.0003]:
                    for dm in [0.00003, 0.00005, 0.0001]:
                        yield {
                            "t_entry": t,
                            "delta_full": df,
                            "delta_half": dh,
                            "delta_min": dm,
                            "use_oracle_veto": False,
                        }, f"t{t}_df{df}_dh{dh}_dm{dm}"
