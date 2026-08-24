"""Core backtest loop."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np

from .market import Market
from .sizing import SizingConfig, size_trade, taker_fee_per_share


@dataclass(slots=True)
class Signal:
    side: str  # "YES" or "NO"
    entry_idx: int
    exit_idx: Optional[int] = None  # None = hold to resolution
    confidence: float = 1.0
    reason: str = ""


@dataclass(slots=True)
class Trade:
    market_id: str
    strategy: str
    side: str
    entry_time: float
    entry_price: float
    shares: int
    exit_time: float
    exit_price: float
    fee_paid: float
    pnl: float
    reason: str


def backtest_market(
    strategy_name: str,
    market: Market,
    signals: List[Signal],
    sizing: SizingConfig,
    initial_balance: float,
) -> List[Trade]:
    """Execute a list of signals on one market sequentially."""
    trades: List[Trade] = []
    balance = initial_balance

    for sig in signals:
        if sig.entry_idx < 0 or sig.entry_idx >= len(market):
            continue
        # Entry price = best ask of chosen side
        if sig.side == "YES":
            entry_price = float(market.best_ask_up[sig.entry_idx])
        else:
            entry_price = float(market.best_ask_down[sig.entry_idx])
        if np.isnan(entry_price) or entry_price <= 0 or entry_price >= 1.0:
            continue

        shares = size_trade(balance, entry_price, sizing)
        if shares <= 0:
            continue

        entry_cost = shares * entry_price
        entry_fee = shares * taker_fee_per_share(entry_price, sizing.fee_multiplier)
        if entry_cost + entry_fee > balance:
            continue

        # Determine exit
        if sig.exit_idx is None or sig.exit_idx >= len(market):
            exit_idx = len(market) - 1
            exit_time = market.end_ts
            # Resolution payout
            exit_price = 1.0 if market.resolution == sig.side else 0.0
        else:
            exit_idx = sig.exit_idx
            exit_time = float(market.ts[exit_idx])
            if sig.side == "YES":
                exit_price = float(market.best_bid_up[exit_idx])
            else:
                exit_price = float(market.best_bid_down[exit_idx])
            if np.isnan(exit_price):
                exit_price = market.price_up[exit_idx] if sig.side == "YES" else market.price_down[exit_idx]
                if np.isnan(exit_price):
                    exit_price = 1.0 if market.resolution == sig.side else 0.0

        proceeds = shares * exit_price
        pnl = proceeds - entry_cost - entry_fee

        # Update balance only on completed trade
        balance += pnl
        if balance <= 0:
            balance = 0.0

        trades.append(
            Trade(
                market_id=market.market_id,
                strategy=strategy_name,
                side=sig.side,
                entry_time=float(market.ts[sig.entry_idx]),
                entry_price=entry_price,
                shares=shares,
                exit_time=exit_time,
                exit_price=exit_price,
                fee_paid=entry_fee,
                pnl=pnl,
                reason=sig.reason,
            )
        )
    return trades


def run_strategy(
    strategy,
    markets: List[Market],
    sizing: SizingConfig,
    initial_balance: float,
) -> List[Trade]:
    """Run a Strategy object across all markets."""
    all_trades: List[Trade] = []
    balance = initial_balance
    for market in markets:
        signals = strategy.generate_signals(market)
        trades = backtest_market(strategy.name, market, signals, sizing, balance)
        all_trades.extend(trades)
        if trades:
            balance += sum(t.pnl for t in trades)
            if balance <= 0:
                break
    return all_trades
