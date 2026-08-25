"""Strategy 61: Session-Only Engine Restriction.
Gate S21 Window-Delta Purist signals by UTC hour expectancy.
A precomputed hour_map maps UTC hour -> (expectancy, sample_count).
Only allow the S21 signal when the entry hour's expectancy is at least
min_expectancy and is based on at least min_samples historical observations.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.backtest import Signal
from engine.market import Market
from strategies.base import Strategy
from strategies.s21_window_delta_purist import S21WindowDeltaPurist


# Flat permissive default. Replace with a trained map for real use.
DEFAULT_HOUR_MAP: Dict[int, Tuple[float, int]] = {
    h: (0.52, 1000) for h in range(24)
}


class S61SessionOnlyEngineRestriction(Strategy):
    name = "S61_SessionOnly_Engine_Restriction"

    def __init__(
        self,
        t_entry: float = 10.0,
        delta_full: float = 0.001,
        delta_half: float = 0.0002,
        delta_min: float = 0.00005,
        use_oracle_veto: bool = False,
        min_expectancy: float = 0.52,
        min_samples: int = 30,
        hour_map: Optional[Dict[int, Tuple[float, int]]] = None,
    ):
        self.s21 = S21WindowDeltaPurist(
            t_entry=t_entry,
            delta_full=delta_full,
            delta_half=delta_half,
            delta_min=delta_min,
            use_oracle_veto=use_oracle_veto,
        )
        self.params = {
            "t_entry": t_entry,
            "delta_full": delta_full,
            "delta_half": delta_half,
            "delta_min": delta_min,
            "use_oracle_veto": use_oracle_veto,
            "min_expectancy": min_expectancy,
            "min_samples": min_samples,
            "hour_map": hour_map if hour_map is not None else DEFAULT_HOUR_MAP.copy(),
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        signals = self.s21.generate_signals(market)
        if not signals:
            return []

        sig = signals[0]
        entry_ts = market.ts[sig.entry_idx]
        hour = int(datetime.fromtimestamp(float(entry_ts), tz=timezone.utc).hour)

        hour_map = p["hour_map"]
        expectancy, n_samples = hour_map.get(hour, (0.0, 0))
        if n_samples < p["min_samples"] or expectancy < p["min_expectancy"]:
            return []

        sig.reason = (
            f"{sig.reason} | session_filter hour={hour:02d} "
            f"exp={expectancy:.3f} n={n_samples}"
        )
        return [sig]

    def param_sweep(self):
        hour_map = self.params.get("hour_map", DEFAULT_HOUR_MAP.copy())
        for t in [5, 10, 15]:
            for dm in [0.00003, 0.00005, 0.0001]:
                for me in [0.50, 0.52, 0.55]:
                    yield {
                        "t_entry": t,
                        "delta_full": 0.001,
                        "delta_half": 0.0002,
                        "delta_min": dm,
                        "use_oracle_veto": False,
                        "min_expectancy": me,
                        "min_samples": 30,
                        "hour_map": hour_map,
                    }, f"t{t}_dm{dm}_me{me}"
