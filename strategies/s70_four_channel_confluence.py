"""Strategy 70: Four-Channel Confluence.
Four independent channels vote -1/+1; enter when the weighted composite
magnitude crosses an entry threshold and the token ask is cheap enough.
"""
import numpy as np
from typing import List

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


class S70FourChannelConfluence(Strategy):
    name = "S70_Four_Channel_Confluence"

    def __init__(
        self,
        window: int = 10,
        delta_scale: float = 0.001,
        spread_max: float = 0.05,
        pressure_scale: float = 0.01,
        weights: dict = None,
        entry_threshold: float = 0.40,
        max_price: float = 0.70,
    ):
        if weights is None:
            weights = {
                "sentiment": 1.0,
                "liquidity": 0.8,
                "pressure": 0.8,
                "momentum": 0.6,
            }
        self.params = {
            "window": window,
            "delta_scale": delta_scale,
            "spread_max": spread_max,
            "pressure_scale": pressure_scale,
            "weights": dict(weights),
            "entry_threshold": entry_threshold,
            "max_price": max_price,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        w = p["window"]
        if n < w + 5:
            return []

        weights = p["weights"]
        total_weight = sum(weights.values())
        if total_weight <= 1e-12:
            return []

        # Channel 1: Sentiment from spot-vs-strike delta.
        sentiment = np.clip(
            market.delta_pct / p["delta_scale"], -1.0, 1.0
        )

        # Channel 2: Liquidity from spread tightness, signed by delta direction.
        spread_up = market.best_ask_up - market.best_bid_up
        spread_down = market.best_ask_down - market.best_bid_down
        mid_up = (market.best_bid_up + market.best_ask_up) * 0.5
        mid_down = (market.best_bid_down + market.best_ask_down) * 0.5
        with np.errstate(divide="ignore", invalid="ignore"):
            tightness_up = 1.0 - np.clip(spread_up / (p["spread_max"] * mid_up), 0.0, 1.0)
            tightness_down = 1.0 - np.clip(spread_down / (p["spread_max"] * mid_down), 0.0, 1.0)
        tightness_up = np.where(np.isfinite(tightness_up), tightness_up, 0.0)
        tightness_down = np.where(np.isfinite(tightness_down), tightness_down, 0.0)
        liquidity = np.where(
            market.delta_pct >= 0,
            tightness_up,
            -tightness_down,
        )

        # Channel 3: Supply-demand pressure from top-of-book mid migration.
        mid_up_change = np.zeros(n)
        mid_down_change = np.zeros(n)
        mid_up_change[1:] = mid_up[1:] - mid_up[:-1]
        mid_down_change[1:] = mid_down[1:] - mid_down[:-1]
        pressure = np.where(
            market.delta_pct >= 0,
            np.clip(mid_up_change / p["pressure_scale"], -1.0, 1.0),
            np.clip(-mid_down_change / p["pressure_scale"], -1.0, 1.0),
        )

        # Channel 4: Volatility-adjusted momentum from spot returns.
        returns = np.zeros(n)
        returns[w:] = (market.spot[w:] - market.spot[:-w]) / market.spot[:-w]
        vol = np.zeros(n)
        for i in range(w, n):
            chunk = market.spot[i - w + 1 : i + 1]
            pct_changes = np.diff(chunk) / chunk[:-1]
            v = float(np.std(pct_changes)) if len(pct_changes) > 0 else 0.0
            vol[i] = v
        with np.errstate(divide="ignore", invalid="ignore"):
            momentum = np.where(
                vol > 1e-12,
                np.clip(returns / (vol + 1e-12), -1.0, 1.0),
                0.0,
            )
        momentum = np.where(np.isfinite(momentum), momentum, 0.0)

        # Composite weighted mean at each bar.
        composite = (
            weights["sentiment"] * sentiment
            + weights["liquidity"] * liquidity
            + weights["pressure"] * pressure
            + weights["momentum"] * momentum
        ) / total_weight

        for idx in range(w, n - 1):
            comp = float(composite[idx])
            if abs(comp) < p["entry_threshold"]:
                continue

            side = "YES" if comp > 0 else "NO"
            ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
            if np.isnan(ask) or ask <= 0 or ask > p["max_price"]:
                continue

            reason = (
                f"four_channel_confluence side={side} composite={comp:.3f} "
                f"s={sentiment[idx]:.2f} l={liquidity[idx]:.2f} "
                f"p={pressure[idx]:.2f} m={momentum[idx]:.2f} ask={ask:.3f}"
            )
            return [Signal(side=side, entry_idx=idx, reason=reason)]

        return []

    def param_sweep(self):
        weights_sets = [
            {"sentiment": 1.0, "liquidity": 0.8, "pressure": 0.8, "momentum": 0.6},
            {"sentiment": 1.0, "liquidity": 1.0, "pressure": 1.0, "momentum": 1.0},
        ]
        for w in [5, 10, 15]:
            for et in [0.30, 0.40, 0.50]:
                for mp in [0.60, 0.70, 0.80]:
                    for weights in weights_sets:
                        yield {
                            "window": w,
                            "delta_scale": 0.001,
                            "spread_max": 0.05,
                            "pressure_scale": 0.01,
                            "weights": dict(weights),
                            "entry_threshold": et,
                            "max_price": mp,
                        }, f"w{w}_et{et}_mp{mp}_wset{list(weights.values())}"
