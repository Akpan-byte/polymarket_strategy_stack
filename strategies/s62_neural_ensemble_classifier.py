"""Strategy 62: 9-Feature Neural Ensemble Classifier.

Approximates a neural ensemble with three fixed-coefficient logistic experts.
Features: RSI, EMA cross, Bollinger %B, returns, candle proxy, volume-pressure
proxy, YES delta, YES ask momentum, NO ask momentum.
"""
import numpy as np
from typing import List

from engine.market import Market
from engine.backtest import Signal
from strategies.base import Strategy


def _rsi(series: np.ndarray, window: int) -> np.ndarray:
    n = series.shape[0]
    diffs = np.diff(series)
    gains = np.maximum(diffs, 0.0)
    losses = -np.minimum(diffs, 0.0)
    cum_gain = np.cumsum(gains)
    cum_loss = np.cumsum(losses)
    rsi = np.full(n, np.nan)
    for idx in range(window + 1, n):
        g = cum_gain[idx - 1] - (cum_gain[idx - window - 1] if idx - window - 1 >= 0 else 0.0)
        l = cum_loss[idx - 1] - (cum_loss[idx - window - 1] if idx - window - 1 >= 0 else 0.0)
        avg_g = g / window
        avg_l = l / window
        if avg_l <= 1e-12:
            rsi[idx] = 100.0 if avg_g > 1e-12 else 50.0
        else:
            rsi[idx] = 100.0 - 100.0 / (1.0 + avg_g / avg_l)
    return rsi


def _ema(series: np.ndarray, window: int) -> np.ndarray:
    alpha = 2.0 / (window + 1.0)
    out = np.empty_like(series)
    out[0] = series[0]
    for i in range(1, series.shape[0]):
        out[i] = alpha * series[i] + (1.0 - alpha) * out[i - 1]
    return out


def _rolling_mean_std(series: np.ndarray, window: int):
    n = series.shape[0]
    cum = np.cumsum(series)
    cum_sq = np.cumsum(series ** 2)
    mean = (cum[window - 1:] - np.concatenate(([0.0], cum[: n - window]))) / window
    var = (cum_sq[window - 1:] - np.concatenate(([0.0], cum_sq[: n - window]))) / window - mean ** 2
    var = np.where(var < 0, 0, var)
    std = np.sqrt(var)
    pad = np.full(window - 1, np.nan)
    mean = np.concatenate((pad, mean))
    std = np.concatenate((pad, std))
    return mean, std


def _logistic(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


class S62NeuralEnsembleClassifier(Strategy):
    name = "S62_Neural_Ensemble_Classifier"

    def __init__(
        self,
        margin: float = 0.02,
        rsi_window: int = 14,
        bb_window: int = 20,
        bb_std: float = 2.0,
        ema_fast: int = 12,
        ema_slow: int = 26,
        return_window: int = 10,
        pressure_window: int = 10,
        max_price: float = 0.70,
        ensemble_weights=None,
    ):
        if ensemble_weights is None:
            ensemble_weights = [0.50, 0.30, 0.20]
        self.params = {
            "margin": margin,
            "rsi_window": rsi_window,
            "bb_window": bb_window,
            "bb_std": bb_std,
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "return_window": return_window,
            "pressure_window": pressure_window,
            "max_price": max_price,
            "ensemble_weights": ensemble_weights,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        min_idx = max(
            p["rsi_window"],
            p["bb_window"],
            p["ema_slow"],
            p["return_window"],
            p["pressure_window"],
        ) + 2
        if n < min_idx + 10:
            return []

        spot = market.spot

        # 1. RSI normalised to [0, 1]
        rsi = _rsi(spot, p["rsi_window"]) / 100.0

        # 2. EMA cross normalised by spot
        ema_fast = _ema(spot, p["ema_fast"])
        ema_slow = _ema(spot, p["ema_slow"])
        ema_cross = (ema_fast - ema_slow) / (spot + 1e-12)

        # 3. Bollinger %B
        mean, std = _rolling_mean_std(spot, p["bb_window"])
        upper = mean + p["bb_std"] * std
        lower = mean - p["bb_std"] * std
        band_width = upper - lower
        pct_b = np.full(n, 0.5)
        valid_band = band_width > 1e-12
        pct_b[valid_band] = (spot[valid_band] - lower[valid_band]) / band_width[valid_band]
        pct_b = np.clip(pct_b, 0.0, 1.0)

        # Helpers for lagged series
        rw = p["return_window"]
        pw = p["pressure_window"]

        def lagged(s, w):
            out = np.full_like(s, np.nan)
            out[w:] = s[:-w]
            return out

        spot_lag = lagged(spot, rw)
        # 4. Returns over return_window
        ret = np.full(n, 0.0)
        valid_ret = spot_lag > 0
        ret[valid_ret] = (spot[valid_ret] - spot_lag[valid_ret]) / spot_lag[valid_ret]

        # 5. Candle proxy: recent move normalised by rolling std
        candle = np.full(n, 0.0)
        valid_candle = (std > 1e-12) & valid_ret
        candle[valid_candle] = (spot[valid_candle] - spot_lag[valid_candle]) / std[valid_candle]

        # 6. Volume-pressure proxy: YES order-book imbalance
        ask_up = market.best_ask_up
        bid_up = market.best_bid_up
        mid_up = 0.5 * (bid_up + ask_up)
        pressure = np.full(n, 0.0)
        denom = bid_up + ask_up
        valid_pressure = denom > 1e-12
        pressure[valid_pressure] = (bid_up[valid_pressure] - ask_up[valid_pressure]) / denom[valid_pressure]

        # 7. YES delta
        yes_delta = market.delta_pct

        # 8 & 9. YES / NO ask momentum over pressure_window
        ask_up_lag = lagged(ask_up, pw)
        ask_down_lag = lagged(market.best_ask_down, pw)
        up_mom = np.full(n, 0.0)
        down_mom = np.full(n, 0.0)
        valid_up = ask_up_lag > 0
        valid_down = ask_down_lag > 0
        up_mom[valid_up] = (ask_up[valid_up] - ask_up_lag[valid_up]) / ask_up_lag[valid_up]
        down_mom[valid_down] = (market.best_ask_down[valid_down] - ask_down_lag[valid_down]) / ask_down_lag[valid_down]

        # Stack features. Each row is the feature vector at that snapshot.
        features = np.column_stack(
            [rsi, ema_cross, pct_b, ret, candle, pressure, yes_delta, up_mom, down_mom]
        )

        # Fixed coefficients for three logistic experts.
        # Expert 0: trend/momentum, Expert 1: mean reversion, Expert 2: microstructure.
        experts = np.array(
            [
                [0.0, 3.0, 0.0, 1.5, 0.0, 0.0, 2.5, 2.0, -1.5],  # trend
                [2.0, -1.5, -3.0, -0.5, -1.0, 0.0, -1.0, 0.0, 0.0],  # mean reversion
                [0.0, 0.0, 0.0, 0.0, 0.0, 2.5, 0.0, 1.0, -1.0],  # microstructure
            ],
            dtype=float,
        )

        # Compute expert logits and ensemble probability of YES.
        logits = features @ experts.T  # shape (n, 3)
        probs = _logistic(logits)
        w = np.array(p["ensemble_weights"], dtype=float)
        w = w / w.sum()
        ensemble = probs @ w  # shape (n,)

        signals: List[Signal] = []
        for idx in range(min_idx, n - 5):
            p_yes = ensemble[idx]
            p_no = 1.0 - p_yes
            ask_yes = market.best_ask_up[idx]
            ask_no = market.best_ask_down[idx]

            side = None
            if not np.isnan(ask_yes) and 0 < ask_yes < 1.0 and ask_yes <= p["max_price"]:
                if p_yes >= ask_yes + p["margin"]:
                    side = "YES"
            if side is None and not np.isnan(ask_no) and 0 < ask_no < 1.0 and ask_no <= p["max_price"]:
                if p_no >= ask_no + p["margin"]:
                    side = "NO"

            if side is None:
                continue

            # Exit when the ensemble flips to the opposite side.
            exit_idx = None
            if side == "YES":
                flip = np.where(ensemble[idx + 1 :] < 0.5)[0]
            else:
                flip = np.where(ensemble[idx + 1 :] > 0.5)[0]
            if flip.size > 0:
                exit_idx = int(idx + 1 + flip[0])

            reason = (
                f"neural_ensemble side={side} P_yes={p_yes:.3f} "
                f"ask_yes={ask_yes:.3f} ask_no={ask_no:.3f} margin={p['margin']}"
            )
            signals.append(Signal(side=side, entry_idx=idx, exit_idx=exit_idx, reason=reason))
            # Only one signal per market.
            break

        return signals

    def param_sweep(self):
        for margin in [0.01, 0.02, 0.03]:
            for rsi_window in [10, 14, 20]:
                for bb_window in [15, 20, 25]:
                    yield {
                        "margin": margin,
                        "rsi_window": rsi_window,
                        "bb_window": bb_window,
                        "bb_std": 2.0,
                        "ema_fast": 12,
                        "ema_slow": 26,
                        "return_window": 10,
                        "pressure_window": 10,
                        "max_price": 0.70,
                        "ensemble_weights": [0.50, 0.30, 0.20],
                    }, f"m{margin}_rsi{rsi_window}_bb{bb_window}"
