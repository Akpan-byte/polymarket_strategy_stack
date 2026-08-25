"""Strategy 56: Whale-Wallet On-Chain Front-Run.
Proxy whale activity by combining early-window token-price velocity with
top-of-book orderbook pressure. Enter within the first two minutes when both
footprints align on one side, then hold to resolution.
"""
import numpy as np
from typing import List

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


def _linreg_slope(x: np.ndarray, y: np.ndarray) -> float:
    """Return the OLS slope of y vs x, robust to NaNs."""
    mask = ~(np.isnan(x) | np.isnan(y))
    xv = x[mask]
    yv = y[mask]
    if len(xv) < 2:
        return 0.0
    xm = xv - np.mean(xv)
    denom = np.sum(xm * xm)
    if denom <= 1e-18:
        return 0.0
    return np.sum(xm * (yv - np.mean(yv))) / denom


class S56WhaleWalletOnchainFrontrun(Strategy):
    name = "S56_Whale_Wallet_OnChain_FrontRun"

    def __init__(
        self,
        early_sec: float = 120.0,
        min_ticks: int = 3,
        velocity_threshold: float = 0.0001,
        pressure_threshold: float = 0.005,
        dominance_margin: float = 0.0,
        max_token_price: float = 0.65,
    ):
        self.params = {
            "early_sec": early_sec,
            "min_ticks": min_ticks,
            "velocity_threshold": velocity_threshold,
            "pressure_threshold": pressure_threshold,
            "dominance_margin": dominance_margin,
            "max_token_price": max_token_price,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        if n < p["min_ticks"]:
            return []

        elapsed = market.elapsed_sec

        # Last index still inside the early window.
        last_idx = int(np.searchsorted(elapsed, p["early_sec"], side="right")) - 1
        if last_idx < p["min_ticks"] - 1:
            return []

        best_bid_up = market.best_bid_up
        best_ask_up = market.best_ask_up
        price_up = market.price_up
        best_bid_down = market.best_bid_down
        best_ask_down = market.best_ask_down
        price_down = market.price_down

        # Per-tick top-of-book pressure proxies.
        # Bid rising + ask tightening + token price rising = positive pressure.
        pressure_up = np.zeros(n)
        pressure_down = np.zeros(n)
        for i in range(1, n):
            if not (np.isnan(best_bid_up[i]) or np.isnan(best_bid_up[i - 1]) or
                    np.isnan(best_ask_up[i]) or np.isnan(best_ask_up[i - 1]) or
                    np.isnan(price_up[i]) or np.isnan(price_up[i - 1])):
                pressure_up[i] = (
                    (best_bid_up[i] - best_bid_up[i - 1])
                    + (best_ask_up[i - 1] - best_ask_up[i])
                    + (price_up[i] - price_up[i - 1])
                )
            if not (np.isnan(best_bid_down[i]) or np.isnan(best_bid_down[i - 1]) or
                    np.isnan(best_ask_down[i]) or np.isnan(best_ask_down[i - 1]) or
                    np.isnan(price_down[i]) or np.isnan(price_down[i - 1])):
                pressure_down[i] = (
                    (best_bid_down[i] - best_bid_down[i - 1])
                    + (best_ask_down[i - 1] - best_ask_down[i])
                    + (price_down[i] - price_down[i - 1])
                )

        # Scan the early window and enter on the first confirmed tick.
        for idx in range(p["min_ticks"] - 1, last_idx + 1):
            window = slice(0, idx + 1)
            e = elapsed[window]

            # Token-price velocity for each side.
            v_up = _linreg_slope(e, price_up[window])
            v_down = _linreg_slope(e, price_down[window])

            side = None
            if v_up > p["velocity_threshold"] and v_up > v_down + p["dominance_margin"]:
                side = "YES"
            elif v_down > p["velocity_threshold"] and v_down > v_up + p["dominance_margin"]:
                side = "NO"

            if side is None:
                continue

            # Cumulative orderbook pressure over the window.
            p_up = float(np.sum(pressure_up[1:idx + 1]))
            p_down = float(np.sum(pressure_down[1:idx + 1]))

            if side == "YES":
                if p_up < p["pressure_threshold"]:
                    continue
                if p_up < p_down + p["dominance_margin"]:
                    continue
                ask = market.best_ask_up[idx]
            else:
                if p_down < p["pressure_threshold"]:
                    continue
                if p_down < p_up + p["dominance_margin"]:
                    continue
                ask = market.best_ask_down[idx]

            if np.isnan(ask) or ask <= 0 or ask > p["max_token_price"]:
                continue

            reason = (
                f"whale_front_run side={side} v_up={v_up:.4%}/s v_down={v_down:.4%}/s "
                f"pressure_up={p_up:.4f} pressure_down={p_down:.4f} ask={ask:.3f}"
            )
            return [Signal(side=side, entry_idx=idx, reason=reason)]

        return []

    def param_sweep(self):
        for es in [90, 120, 150]:
            for vt in [0.0001, 0.0002]:
                for pt in [0.003, 0.005]:
                    for dm in [0.0]:
                        for mp in [0.60, 0.65]:
                            yield {
                                "early_sec": es,
                                "min_ticks": 3,
                                "velocity_threshold": vt,
                                "pressure_threshold": pt,
                                "dominance_margin": dm,
                                "max_token_price": mp,
                            }, f"es{es}_vt{vt}_pt{pt}_dm{dm}_mp{mp}"
