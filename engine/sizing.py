"""Position sizing and fee utilities."""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True, slots=True)
class SizingConfig:
    mode: str  # "fixed" | "pct_min" | "kelly_quarter"
    initial_balance: float
    fixed_dollar: float = 1.0
    pct: float = 0.005
    min_shares: int = 5
    fee_multiplier: float = 0.25
    kelly_init_pct: float = 0.02  # used until enough history
    kelly_min_trades: int = 10

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "initial_balance": self.initial_balance,
            "fixed_dollar": self.fixed_dollar,
            "pct": self.pct,
            "min_shares": self.min_shares,
        }


def taker_fee_per_share(price: float, fee_multiplier: float = 0.25) -> float:
    """Polymarket short-crypto taker fee."""
    if price <= 0 or price >= 1:
        return 0.0
    return price * fee_multiplier * (price * (1.0 - price)) ** 2


class KellyState:
    """Running state for quarter-Kelly position sizing."""
    __slots__ = ("wins", "losses", "win_amt", "loss_amt")

    def __init__(self):
        self.wins = 0
        self.losses = 0
        self.win_amt = 0.0
        self.loss_amt = 0.0

    def update(self, pnl: float):
        if pnl > 0:
            self.wins += 1
            self.win_amt += pnl
        else:
            self.losses += 1
            self.loss_amt += abs(pnl)

    def fraction(self, min_trades: int = 10) -> float:
        n = self.wins + self.losses
        if n < min_trades:
            return 0.0
        p = self.wins / n
        avg_win = self.win_amt / self.wins if self.wins else 0.0
        avg_loss = self.loss_amt / self.losses if self.losses else 0.0
        if avg_loss <= 1e-12 or avg_win <= 1e-12:
            return 0.0
        b = avg_win / avg_loss
        if b <= 0.0:
            return 0.0
        kelly = (p * b - (1.0 - p)) / b
        return max(0.0, kelly) / 4.0


def size_trade(
    balance: float,
    entry_price: float,
    config: SizingConfig,
) -> int:
    """Return number of shares to buy (rounded to min_shares)."""
    if config.mode == "fixed":
        dollars = config.fixed_dollar
    elif config.mode == "pct_min":
        dollars = max(config.initial_balance * config.pct, config.min_shares * entry_price)
    else:
        dollars = config.fixed_dollar

    # Don't exceed balance
    raw_shares = int(math.floor(min(dollars, balance) / max(entry_price, 1e-9)))
    if raw_shares < config.min_shares:
        return 0
    # Round down to nearest min_shares multiple
    shares = (raw_shares // config.min_shares) * config.min_shares
    return shares


def kelly_size(
    balance: float,
    entry_price: float,
    config: SizingConfig,
    state: KellyState,
) -> int:
    """Return shares using quarter-Kelly of current balance."""
    if entry_price <= 0.0 or entry_price >= 1.0 or balance <= 0.0:
        return 0
    f = state.fraction(config.kelly_min_trades)
    if f <= 0.0:
        # Not enough history: use initial pct of balance
        dollars = config.initial_balance * config.kelly_init_pct
    else:
        dollars = balance * f
    # Enforce 5-contract minimum dollar value
    min_dollars = config.min_shares * entry_price
    dollars = max(dollars, min_dollars)
    raw_shares = int(math.floor(min(dollars, balance) / max(entry_price, 1e-9)))
    if raw_shares < config.min_shares:
        return 0
    return (raw_shares // config.min_shares) * config.min_shares


DEFAULT_SIZINGS = {
    "s1_fixed_200": SizingConfig("fixed", 200.0, fixed_dollar=1.0),
    "s2_pctmin_200": SizingConfig("pct_min", 200.0, pct=0.005, min_shares=5),
    "s3_pctmin_150": SizingConfig("pct_min", 150.0, pct=0.005, min_shares=5),
    "s4_kelly_quarter_200": SizingConfig("kelly_quarter", 200.0, min_shares=5, kelly_init_pct=0.02, kelly_min_trades=10),
}
