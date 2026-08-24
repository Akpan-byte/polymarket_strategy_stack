"""Base strategy interface."""
from abc import ABC, abstractmethod
from typing import Dict, List

from engine.market import Market
from engine.backtest import Signal


class Strategy(ABC):
    name: str = "base"
    params: Dict = {}

    @abstractmethod
    def generate_signals(self, market: Market) -> List[Signal]:
        """Return signals for a single market. No look-ahead past entry_idx."""
        ...

    def param_sweep(self):
        """Yield (param_dict, label) tuples for grid search. Override per strategy."""
        yield self.params, "default"
