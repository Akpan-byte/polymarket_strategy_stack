"""Position sizing and fee utilities."""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True, slots=True)
class SizingConfig:
    mode: str  # "fixed" | "pct_min"
    initial_balance: float
    fixed_dollar: float = 1.0
    pct: float = 0.005
    min_shares: int = 5
    fee_multiplier: float = 0.25

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


DEFAULT_SIZINGS = {
    "s1_fixed_200": SizingConfig("fixed", 200.0, fixed_dollar=1.0),
    "s2_pctmin_200": SizingConfig("pct_min", 200.0, pct=0.005, min_shares=5),
    "s3_pctmin_150": SizingConfig("pct_min", 150.0, pct=0.005, min_shares=5),
}
