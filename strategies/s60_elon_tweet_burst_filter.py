"""Strategy 60: Elon/Key-Figure Tweet-Burst Filter.
Synthetic tweet burst from a sharp spot move. Enter momentum in the burst
direction if the token has repriced less than a fraction of the expected move.
"""
import numpy as np
from typing import List

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


class S60ElonTweetBurstFilter(Strategy):
    name = "S60_Elon_Tweet_Burst_Filter"

    def __init__(
        self,
        burst_window: int = 5,
        min_delta: float = 0.0005,
        max_repriced_frac: float = 0.5,
        fair_slope: float = 500.0,
        neutral_price: float = 0.5,
        max_price: float = 0.70,
    ):
        self.params = {
            "burst_window": burst_window,
            "min_delta": min_delta,
            "max_repriced_frac": max_repriced_frac,
            "fair_slope": fair_slope,
            "neutral_price": neutral_price,
            "max_price": max_price,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        bw = p["burst_window"]
        if n < bw + 5:
            return []

        spot = market.spot
        price_up = market.price_up
        price_down = market.price_down

        # Spot return over burst_window, aligned to right edge.
        spot_prev = spot[:-bw]
        spot_now = spot[bw:]
        returns = np.concatenate((np.full(bw, np.nan), (spot_now - spot_prev) / spot_prev))

        # Synthetic fair probability from spot delta around the strike.
        fair_yes = _sigmoid(market.delta_pct * p["fair_slope"])
        expected_yes_move = fair_yes - p["neutral_price"]

        actual_yes_move = price_up - p["neutral_price"]
        actual_no_move = price_down - p["neutral_price"]

        for idx in range(bw, n - 5):
            r = returns[idx]
            if np.isnan(r) or abs(r) < p["min_delta"]:
                continue

            side = "YES" if r > 0 else "NO"
            ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
            if np.isnan(ask) or ask <= 0 or ask >= 1.0 or ask > p["max_price"]:
                continue

            if side == "YES":
                exp_move = expected_yes_move[idx]
                act_move = actual_yes_move[idx]
            else:
                exp_move = -expected_yes_move[idx]
                act_move = actual_no_move[idx]

            if abs(exp_move) < 1e-6:
                continue

            repriced = act_move / exp_move
            # Require move in the same direction and not too much repricing.
            if repriced < 0.0 or repriced > p["max_repriced_frac"]:
                continue

            reason = (
                f"burst={r:.4%} over {bw} idx repriced={repriced:.2f} "
                f"side={side} ask={ask:.3f}"
            )
            return [Signal(side=side, entry_idx=idx, reason=reason)]

        return []

    def param_sweep(self):
        for bw in [3, 5, 8]:
            for md in [0.0003, 0.0005, 0.001]:
                for mrf in [0.3, 0.5, 0.7]:
                    yield {
                        "burst_window": bw,
                        "min_delta": md,
                        "max_repriced_frac": mrf,
                        "fair_slope": 500.0,
                        "neutral_price": 0.5,
                        "max_price": 0.70,
                    }, f"bw{bw}_md{md}_mrf{mrf}"
