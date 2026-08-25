"""Strategy 68: Price Field Staged Exits.
Parametric logistic price field based on remaining time and absolute spot delta.
Enter when the best ask is at least `entry_margin` below the field, then split
the position into three equal legs held to window resolution.
"""
import math
import numpy as np
from typing import List

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


def _price_field(rem_sec: float, abs_delta: float, L: float, bias: float,
                 k_t: float, k_d: float) -> float:
    """Logistic price field in (0, L] as a function of rem_sec and |delta|."""
    rem_min = rem_sec / 60.0
    delta_bps = abs_delta * 10000.0  # scale delta to basis points
    z = bias + k_t * rem_min + k_d * delta_bps
    return L / (1.0 + math.exp(-z))


class S68PriceFieldStagedExits(Strategy):
    name = "S68_Price_Field_Staged_Exits"

    def __init__(
        self,
        L: float = 0.85,
        bias: float = 0.10,
        k_t: float = -0.04,
        k_d: float = 0.06,
        entry_margin: float = 0.05,
        min_delta: float = 0.0002,
        max_ask: float = 0.75,
        min_rem_sec: float = 30.0,
        max_rem_sec: float = 240.0,
        n_legs: int = 3,
    ):
        self.params = {
            "L": L,
            "bias": bias,
            "k_t": k_t,
            "k_d": k_d,
            "entry_margin": entry_margin,
            "min_delta": min_delta,
            "max_ask": max_ask,
            "min_rem_sec": min_rem_sec,
            "max_rem_sec": max_rem_sec,
            "n_legs": n_legs,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        if n < 2:
            return []

        # Scan forward; entry decision uses only data at or before idx.
        for idx in range(1, n - 1):
            rem = market.rem_sec[idx]
            if rem < p["min_rem_sec"] or rem > p["max_rem_sec"]:
                continue

            d = market.delta_pct[idx]
            if abs(d) < p["min_delta"]:
                continue

            side = "YES" if d >= 0 else "NO"
            ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
            if np.isnan(ask) or ask <= 0.0 or ask > p["max_ask"]:
                continue

            field = _price_field(
                rem,
                abs(d),
                p["L"],
                p["bias"],
                p["k_t"],
                p["k_d"],
            )
            threshold = field - p["entry_margin"]
            if ask > threshold:
                continue

            # Staged exits are modeled as n equal legs, each held to resolution.
            # exit_idx is intentionally None to avoid look-ahead.
            conf = 1.0 / p["n_legs"]
            signals = []
            for leg in range(1, p["n_legs"] + 1):
                reason = (
                    f"price_field leg={leg}/{p['n_legs']} side={side} "
                    f"ask={ask:.3f} field={field:.3f} threshold={threshold:.3f} "
                    f"rem={rem:.1f}s delta={d:.4%}"
                )
                signals.append(
                    Signal(
                        side=side,
                        entry_idx=idx,
                        exit_idx=None,
                        confidence=conf,
                        reason=reason,
                    )
                )
            return signals

        return []

    def param_sweep(self):
        for L in [0.80, 0.85, 0.90]:
            for bias in [-0.40, -0.30, -0.20]:
                for k_t in [-0.12, -0.08, -0.04]:
                    for k_d in [0.010, 0.015, 0.020]:
                        for entry_margin in [0.04, 0.05, 0.06]:
                            yield {
                                "L": L,
                                "bias": bias,
                                "k_t": k_t,
                                "k_d": k_d,
                                "entry_margin": entry_margin,
                                "min_delta": self.params["min_delta"],
                                "max_ask": self.params["max_ask"],
                                "min_rem_sec": self.params["min_rem_sec"],
                                "max_rem_sec": self.params["max_rem_sec"],
                                "n_legs": self.params["n_legs"],
                            }, f"L{L}_b{bias}_kt{k_t}_kd{k_d}_m{entry_margin}"
