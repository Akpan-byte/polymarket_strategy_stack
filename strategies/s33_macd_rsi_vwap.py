"""Strategy 33: MACD + RSI + VWAP Stack.
A three-indicator confirmation stack.  All three must agree before entry.
Because raw trade volume is unavailable, VWAP is approximated by a time-
weighted average (TWAP) of the token price over a rolling lookback.
"""
import numpy as np
from typing import List
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


def _twap_proxy(ts: np.ndarray, prices: np.ndarray, window_sec: float) -> np.ndarray:
    """Rolling time-weighted average price used as a VWAP proxy (no volume)."""
    n = len(ts)
    twap = np.full(n, np.nan, dtype=np.float64)
    left = 0
    weighted_sum = 0.0
    dt_sum = 0.0
    for i in range(n):
        while left < i and ts[i] - ts[left] > window_sec:
            dt = ts[left + 1] - ts[left]
            if dt <= 0:
                dt = 1.0
            weighted_sum -= prices[left] * dt
            dt_sum -= dt
            left += 1
        dt = ts[i] - ts[i - 1] if i > 0 else 1.0
        if dt <= 0:
            dt = 1.0
        weighted_sum += prices[i] * dt
        dt_sum += dt
        twap[i] = weighted_sum / dt_sum if dt_sum > 0 else prices[i]
    return twap


class S33MacdRsiVwap(Strategy):
    name = "S33_MACD_RSI_VWAP_Stack"

    def __init__(self, macd_fast: int = 12, macd_slow: int = 26, macd_signal: int = 9,
                 rsi_window: int = 14, rsi_low: float = 40.0, rsi_high: float = 60.0,
                 vwap_window_sec: float = 60.0, min_delta: float = 0.0002,
                 max_price: float = 0.75):
        self.params = {
            "macd_fast": macd_fast,
            "macd_slow": macd_slow,
            "macd_signal": macd_signal,
            "rsi_window": rsi_window,
            "rsi_low": rsi_low,
            "rsi_high": rsi_high,
            "vwap_window_sec": vwap_window_sec,
            "min_delta": min_delta,
            "max_price": max_price,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        warm_up = max(p["macd_slow"], p["rsi_window"]) + 5
        if n < warm_up + 5:
            return []

        # Pre-compute indicators for both sides.
        indicators = {}
        for side, prices in (("YES", market.price_up), ("NO", market.price_down)):
            if np.isnan(prices).any():
                indicators[side] = None
                continue
            ema_fast = _ema(prices, p["macd_fast"])
            ema_slow = _ema(prices, p["macd_slow"])
            macd_line = ema_fast - ema_slow
            signal_line = _ema(macd_line, p["macd_signal"])
            hist = macd_line - signal_line
            rsi = _rsi(prices, p["rsi_window"])
            twap = _twap_proxy(market.ts, prices, p["vwap_window_sec"])
            indicators[side] = {
                "prices": prices,
                "hist": hist,
                "rsi": rsi,
                "twap": twap,
            }

        for idx in range(warm_up, n - 5):
            d = market.delta_pct[idx]
            if abs(d) < p["min_delta"]:
                continue
            side = "YES" if d > 0 else "NO"
            ind = indicators.get(side)
            if ind is None:
                continue

            # MACD confirmation.
            hist = ind["hist"][idx]
            if side == "YES" and hist <= 0:
                continue
            if side == "NO" and hist >= 0:
                continue

            # RSI confirmation (directional but not extreme).
            r = ind["rsi"][idx]
            if np.isnan(r):
                continue
            if side == "YES" and not (50.0 <= r <= p["rsi_high"]):
                continue
            if side == "NO" and not (p["rsi_low"] <= r <= 50.0):
                continue

            # VWAP/TWAP confirmation.
            twap = ind["twap"][idx]
            if np.isnan(twap):
                continue
            if side == "YES" and ind["prices"][idx] <= twap:
                continue
            if side == "NO" and ind["prices"][idx] >= twap:
                continue

            ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
            if np.isnan(ask) or ask > p["max_price"]:
                continue

            return [Signal(
                side=side,
                entry_idx=idx,
                reason=f"macd_rsi_vwap hist={hist:.3f} rsi={r:.1f}",
            )]
        return []

    def param_sweep(self):
        for mf in [8, 12]:
            for ms in [21, 26]:
                for sig in [9]:
                    for rw in [10, 14]:
                        for rl in [35, 40]:
                            for rh in [60, 65]:
                                for vw in [30.0, 60.0]:
                                    for md in [0.0002, 0.0003]:
                                        for mp in [0.65, 0.75]:
                                            yield {
                                                "macd_fast": mf,
                                                "macd_slow": ms,
                                                "macd_signal": sig,
                                                "rsi_window": rw,
                                                "rsi_low": rl,
                                                "rsi_high": rh,
                                                "vwap_window_sec": vw,
                                                "min_delta": md,
                                                "max_price": mp,
                                            }, f"mf{mf}_ms{ms}_sig{sig}_rw{rw}_rl{rl}_rh{rh}_vw{int(vw)}_md{md}_mp{mp}"
