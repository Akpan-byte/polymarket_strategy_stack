"""Strategy 59: Binance Boundary Stop-Hunt Fade.

Fade a fast spot spike-and-stall inside the final two minutes of the window,
entering the opposite side only when the token has overreacted by a meaningful
amount relative to the recent baseline.
"""
import numpy as np
from typing import List

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S59BinanceBoundaryStopHuntFade(Strategy):
    name = "S59_Binance_Boundary_StopHunt_Fade"

    def __init__(
        self,
        spike_pct: float = 0.0010,
        avg_lookback_sec: float = 90.0,
        spike_ratio: float = 2.5,
        token_react: float = 0.08,
        max_price: float = 0.75,
        max_divergence_sec: float = 60.0,
    ):
        self.params = {
            "spike_pct": spike_pct,
            "avg_lookback_sec": avg_lookback_sec,
            "spike_ratio": spike_ratio,
            "token_react": token_react,
            "max_price": max_price,
            "max_divergence_sec": max_divergence_sec,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        if n < 10:
            return []

        elapsed = market.elapsed_sec
        rem = market.rem_sec
        spot = market.spot
        strike = market.strike
        delta = market.delta_pct

        # Index whose elapsed time is ~30s before each snapshot.
        lag30 = np.searchsorted(elapsed, elapsed - 30.0, side="right") - 1
        lag30 = np.maximum(lag30, 0)

        # 30-second spot move (in percent terms) at each index.
        move30 = np.full(n, np.nan)
        valid_lag = np.where(elapsed - elapsed[lag30] >= 25.0)[0]
        move30[valid_lag] = delta[valid_lag] - delta[lag30[valid_lag]]

        abs_move30 = np.abs(move30)

        for idx in range(1, n):
            # Only trade in the final two minutes.
            if rem[idx] > 120.0 or rem[idx] < 3.0:
                continue

            j = lag30[idx]
            if elapsed[idx] - elapsed[j] < 25.0:
                continue

            sm = float(move30[idx])
            if np.isnan(sm) or abs(sm) < p["spike_pct"]:
                continue

            # Baseline: average absolute 30s move over the prior lookback window.
            # Use the interval ending 30s before the current bar so the spike
            # itself is not included in the baseline.
            end_t = elapsed[j]
            start_t = end_t - p["avg_lookback_sec"]
            k = int(np.searchsorted(elapsed, start_t, side="left"))
            k = max(0, min(k, j))
            if j - k < 2:
                continue
            baseline = float(np.nanmean(abs_move30[k : j + 1]))
            if np.isnan(baseline) or baseline <= 0.0:
                continue
            if abs(sm) < p["spike_ratio"] * baseline:
                continue

            # Fade the spike.
            side = "NO" if sm > 0 else "YES"

            # Token overreaction: the token we would buy must have moved at least
            # token_react in the direction that makes it cheap.
            token_px = market.price_down if side == "NO" else market.price_up
            if np.isnan(token_px[idx]) or np.isnan(token_px[j]):
                continue
            token_change = float(token_px[idx] - token_px[j])
            if abs(token_change) < p["token_react"]:
                continue

            # Skip if the spot has been marching in the same direction for more
            # than max_divergence_sec (divergence / trend persists too long).
            t_start = elapsed[idx] - p["max_divergence_sec"]
            di = int(np.searchsorted(elapsed, t_start, side="left"))
            di = max(0, di)
            window_moves = move30[di : idx + 1]
            if len(window_moves) > 1:
                signs = np.sign(window_moves)
                # Ignore zero moves; if every non-zero move shares the current
                # sign, the spike is not fresh.
                nonzero = signs[signs != 0.0]
                if len(nonzero) > 0 and np.all(nonzero == np.sign(sm)):
                    continue

            ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
            if np.isnan(ask) or ask <= 0.0 or ask >= 1.0 or ask > p["max_price"]:
                continue

            reason = (
                f"boundary_stop_hunt side={side} move30={sm:.4%} "
                f"baseline={baseline:.4%} token_change={token_change:.3f} "
                f"T-{rem[idx]:.0f}s"
            )
            return [Signal(side=side, entry_idx=idx, reason=reason)]

        return []

    def param_sweep(self):
        for sp in [0.0008, 0.0010, 0.0012]:
            for al in [60.0, 90.0, 120.0]:
                for sr in [2.0, 3.0]:
                    for tr in [0.06, 0.08, 0.10]:
                        for mp in [0.65, 0.75]:
                            yield {
                                "spike_pct": sp,
                                "avg_lookback_sec": al,
                                "spike_ratio": sr,
                                "token_react": tr,
                                "max_price": mp,
                                "max_divergence_sec": 60.0,
                            }, f"sp{sp}_al{al}_sr{sr}_tr{tr}_mp{mp}"
