"""Strategy 45: EMA5/EMA10 Cross + RSI + Stochastic Triple Confirmation.
All three indicators must align for entry, and the position exits on the
opposite EMA cross or holds to window resolution.
"""
import numpy as np
from typing import List, Optional

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


def _ema(arr: np.ndarray, span: int) -> np.ndarray:
    alpha = 2.0 / (span + 1)
    n = len(arr)
    out = np.empty(n, dtype=np.float64)
    out[0] = float(arr[0])
    for i in range(1, n):
        out[i] = alpha * float(arr[i]) + (1.0 - alpha) * out[i - 1]
    return out


def _rsi(prices: np.ndarray, window: int) -> np.ndarray:
    diffs = np.diff(prices)
    gains = np.where(diffs > 0, diffs, 0.0)
    losses = np.where(diffs < 0, -diffs, 0.0)
    alpha = 1.0 / window
    n = len(prices)
    rsi = np.full(n, np.nan, dtype=np.float64)
    if n <= window:
        return rsi
    avg_gain = float(np.mean(gains[:window]))
    avg_loss = float(np.mean(losses[:window]))
    if avg_loss == 0:
        rsi[window] = 100.0
    else:
        rsi[window] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    for i in range(window + 1, n):
        avg_gain = alpha * gains[i - 1] + (1.0 - alpha) * avg_gain
        avg_loss = alpha * losses[i - 1] + (1.0 - alpha) * avg_loss
        if avg_loss == 0:
            rsi[i] = 100.0
        else:
            rsi[i] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return rsi


def _stoch(prices: np.ndarray, k: int, d: int) -> np.ndarray:
    """Stochastic oscillator (%K and %D) using rolling min/max of spot.

    Returns an array of %D values aligned with the right edge of the lookback.
    """
    n = len(prices)
    out = np.full(n, np.nan, dtype=np.float64)
    if n < k + d - 1:
        return out

    pct_k = np.full(n, np.nan, dtype=np.float64)
    for i in range(k - 1, n):
        lo = float(np.min(prices[i - k + 1 : i + 1]))
        hi = float(np.max(prices[i - k + 1 : i + 1]))
        if hi - lo <= 1e-12:
            pct_k[i] = 50.0
        else:
            pct_k[i] = 100.0 * (prices[i] - lo) / (hi - lo)

    # Simple moving average of %K for %D.
    for i in range(k + d - 2, n):
        out[i] = float(np.mean(pct_k[i - d + 1 : i + 1]))
    return out


def _find_cross(ema_fast: np.ndarray, ema_slow: np.ndarray,
                start: int, end: int, bullish: bool) -> Optional[int]:
    """Return first index in [start, end) with the requested cross."""
    for i in range(max(1, start), min(end, len(ema_fast))):
        if bullish:
            if ema_fast[i] > ema_slow[i] and ema_fast[i - 1] <= ema_slow[i - 1]:
                return i
        else:
            if ema_fast[i] < ema_slow[i] and ema_fast[i - 1] >= ema_slow[i - 1]:
                return i
    return None


class S45EmaRsiStochTripleConfirmation(Strategy):
    name = "S45_EMA_RSI_Stoch_Triple_Confirmation"

    def __init__(
        self,
        ema_fast: int = 5,
        ema_slow: int = 10,
        rsi_window: int = 14,
        rsi_yes_low: float = 50.0,
        rsi_yes_high: float = 70.0,
        rsi_no_low: float = 30.0,
        rsi_no_high: float = 50.0,
        stoch_k: int = 5,
        stoch_d: int = 3,
        stoch_low: float = 20.0,
        stoch_high: float = 80.0,
        cross_lookback: int = 3,
        max_price: float = 0.60,
        max_elapsed_sec: float = 300.0,
    ):
        self.params = {
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "rsi_window": rsi_window,
            "rsi_yes_low": rsi_yes_low,
            "rsi_yes_high": rsi_yes_high,
            "rsi_no_low": rsi_no_low,
            "rsi_no_high": rsi_no_high,
            "stoch_k": stoch_k,
            "stoch_d": stoch_d,
            "stoch_low": stoch_low,
            "stoch_high": stoch_high,
            "cross_lookback": cross_lookback,
            "max_price": max_price,
            "max_elapsed_sec": max_elapsed_sec,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        warm_up = max(p["ema_slow"], p["rsi_window"], p["stoch_k"] + p["stoch_d"] - 1) + 2
        if n < warm_up + p["cross_lookback"] + 5:
            return []

        spot = market.spot
        ema_fast = _ema(spot, p["ema_fast"])
        ema_slow = _ema(spot, p["ema_slow"])
        rsi = _rsi(spot, p["rsi_window"])
        stoch = _stoch(spot, p["stoch_k"], p["stoch_d"])

        for idx in range(warm_up, n - 5):
            # Time filter first (cheapest).
            if market.elapsed_sec[idx] > p["max_elapsed_sec"]:
                continue

            ask_yes = market.best_ask_up[idx]
            ask_no = market.best_ask_down[idx]

            side = None
            # YES entry: bullish EMA cross in lookback, RSI 50-70, stoch rising in bounds.
            if not np.isnan(ask_yes) and ask_yes <= p["max_price"]:
                cross = _find_cross(
                    ema_fast, ema_slow,
                    idx - p["cross_lookback"] + 1, idx + 1, bullish=True,
                )
                if cross is not None:
                    r = rsi[idx]
                    if not np.isnan(r) and p["rsi_yes_low"] <= r <= p["rsi_yes_high"]:
                        s = stoch[idx]
                        s_prev = stoch[idx - 1]
                        if (
                            not np.isnan(s)
                            and not np.isnan(s_prev)
                            and p["stoch_low"] <= s <= p["stoch_high"]
                            and s > s_prev
                        ):
                            side = "YES"

            # NO entry: bearish EMA cross in lookback, RSI 30-50, stoch falling in bounds.
            if side is None and not np.isnan(ask_no) and ask_no <= p["max_price"]:
                cross = _find_cross(
                    ema_fast, ema_slow,
                    idx - p["cross_lookback"] + 1, idx + 1, bullish=False,
                )
                if cross is not None:
                    r = rsi[idx]
                    if not np.isnan(r) and p["rsi_no_low"] <= r <= p["rsi_no_high"]:
                        s = stoch[idx]
                        s_prev = stoch[idx - 1]
                        if (
                            not np.isnan(s)
                            and not np.isnan(s_prev)
                            and p["stoch_low"] <= s <= p["stoch_high"]
                            and s < s_prev
                        ):
                            side = "NO"

            if side is None:
                continue

            ask = ask_yes if side == "YES" else ask_no
            if np.isnan(ask) or ask > p["max_price"]:
                continue

            # Exit on opposite EMA cross; otherwise hold to resolution.
            opposite_bullish = side == "NO"
            exit_idx = _find_cross(
                ema_fast, ema_slow, idx + 1, n, bullish=opposite_bullish
            )

            reason = (
                f"ema_rsi_stoch side={side} ema_cross_within_{p['cross_lookback']} "
                f"rsi={rsi[idx]:.1f} stoch={stoch[idx]:.1f}"
            )
            return [Signal(side=side, entry_idx=idx, exit_idx=exit_idx, reason=reason)]

        return []

    def param_sweep(self):
        for ef in [5, 8]:
            for es in [10, 15]:
                for rw in [10, 14]:
                    for mp in [0.55, 0.60]:
                        for mes in [240.0, 300.0]:
                            yield {
                                "ema_fast": ef,
                                "ema_slow": es,
                                "rsi_window": rw,
                                "rsi_yes_low": 50.0,
                                "rsi_yes_high": 70.0,
                                "rsi_no_low": 30.0,
                                "rsi_no_high": 50.0,
                                "stoch_k": 5,
                                "stoch_d": 3,
                                "stoch_low": 20.0,
                                "stoch_high": 80.0,
                                "cross_lookback": 3,
                                "max_price": mp,
                                "max_elapsed_sec": mes,
                            }, f"ef{ef}_es{es}_rw{rw}_mp{mp}_mes{int(mes)}"
