"""Strategy 49: Markov-Chain State-Transition Prediction.
Discretize realized delta into states, learn a rolling transition matrix, and
enter when the predicted probability of a directional next state clears the
prevailing ask by at least the configured edge.
"""
import numpy as np
from typing import List, Optional, Tuple

from engine.market import Market
from engine.backtest import Signal
from engine.sizing import taker_fee_per_share
from strategies.base import Strategy


class S49MarkovChainStateTransition(Strategy):
    name = "S49_Markov_Chain_State_Transition"

    def __init__(
        self,
        n_states: int = 3,
        history_window: int = 15,
        min_history: int = 10,
        prob_threshold: float = 0.55,
        edge_threshold: float = 0.04,
        max_price: float = 0.70,
        rolling_history_cap: int = 200,
        kill_switch_divergence: float = 0.08,
    ):
        self.params = {
            "n_states": n_states,
            "history_window": history_window,
            "min_history": min_history,
            "prob_threshold": prob_threshold,
            "edge_threshold": edge_threshold,
            "max_price": max_price,
            "rolling_history_cap": rolling_history_cap,
            "kill_switch_divergence": kill_switch_divergence,
        }
        # Persistent state across markets for kill-switch tracking.
        self._predictions: List[Tuple[str, float]] = []  # (side, predicted_prob)
        self._outcomes: List[int] = []  # 1 = win, 0 = loss
        self._last_resolution: Optional[str] = None
        self._kill_switch_active = False

    def _build_states(self, deltas: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Return discrete state series and fixed symmetric bin edges."""
        p = self.params
        n = p["n_states"]
        # Fixed 1% total span avoids look-ahead; extremes clip into buckets 0/n-1.
        edges = np.linspace(-0.01, 0.01, n + 1)
        states = np.searchsorted(edges, deltas, side="right") - 1
        states = np.clip(states, 0, n - 1).astype(np.int64)
        return states, edges

    def _transition_probs(self, states: np.ndarray, current: int) -> np.ndarray:
        """Estimate P(next_state | current) from the recent state history."""
        p = self.params
        window = p["history_window"]
        hist = states[-window:] if len(states) > window else states
        # Count transitions from `current` to any next state.
        from_idx = np.where(hist[:-1] == current)[0]
        if len(from_idx) == 0:
            return np.full(p["n_states"], np.nan)
        next_states = hist[from_idx + 1]
        counts = np.bincount(next_states, minlength=p["n_states"])
        return counts / counts.sum()

    def _check_kill_switch(self) -> bool:
        p = self.params
        n = len(self._outcomes)
        if n < 20:
            return False
        live_wr = np.mean(self._outcomes[-p["rolling_history_cap"]:])
        # Expected WR is the running mean of our predicted probabilities.
        expected_wr = np.mean([prob for _, prob in self._predictions[-p["rolling_history_cap"]:]])
        return abs(live_wr - expected_wr) > p["kill_switch_divergence"]

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        if n < p["min_history"] + 5:
            return []

        # Update outcomes from previous market(s) and evaluate kill switch.
        if self._predictions and self._last_resolution is not None:
            last_market_outcomes = [
                1 if side == self._last_resolution else 0
                for side, _ in self._predictions
            ]
            self._outcomes.extend(last_market_outcomes)
            # Cap outcome history.
            cap = p["rolling_history_cap"]
            self._outcomes = self._outcomes[-cap:]
        if self._check_kill_switch():
            self._kill_switch_active = True
            return []
        self._kill_switch_active = False

        deltas = market.delta_pct
        states, _ = self._build_states(deltas)

        signals: List[Signal] = []
        stored_predictions: List[Tuple[str, float]] = []

        for i in range(p["min_history"], n - 1):
            current = states[i]
            probs = self._transition_probs(states[: i + 1], current)
            if np.any(np.isnan(probs)):
                continue

            next_state = int(np.argmax(probs))
            max_prob = float(probs[next_state])
            if max_prob < p["prob_threshold"]:
                continue

            # Map predicted next state to trade side.
            if next_state > current:
                side = "YES"
            elif next_state < current:
                side = "NO"
            else:
                continue

            # Enter at next window open (i+1), using only data through i.
            entry_idx = i + 1
            ask = market.best_ask_up[entry_idx] if side == "YES" else market.best_ask_down[entry_idx]
            if np.isnan(ask) or ask <= 0 or ask >= 1.0 or ask > p["max_price"]:
                continue

            fee = taker_fee_per_share(ask, 0.25)
            if max_prob - ask - fee < p["edge_threshold"]:
                continue

            reason = (
                f"markov transition state={current}->{next_state} "
                f"p={max_prob:.2f} ask={ask:.3f}"
            )
            signals.append(Signal(side=side, entry_idx=entry_idx, reason=reason))
            stored_predictions.append((side, max_prob))
            # Emit only the first valid signal per market.
            break

        # Store predictions and resolution for evaluation on the next market.
        self._predictions = stored_predictions
        self._last_resolution = market.resolution
        return signals

    def param_sweep(self):
        for ns in [3, 5]:
            for hw in [10, 15]:
                for pt in [0.52, 0.60]:
                    for et in [0.03, 0.05]:
                        for mp in [0.55, 0.70]:
                            yield {
                                "n_states": ns,
                                "history_window": hw,
                                "min_history": hw,
                                "prob_threshold": pt,
                                "edge_threshold": et,
                                "max_price": mp,
                                "rolling_history_cap": 200,
                                "kill_switch_divergence": 0.08,
                            }, f"ns{ns}_hw{hw}_pt{pt}_et{et}_mp{mp}"
