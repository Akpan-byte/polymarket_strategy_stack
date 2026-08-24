"""Metrics computation."""
from __future__ import annotations
import csv
import json
import math
import os
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional
import numpy as np

from .backtest import Trade


def _to_daily_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def compute_metrics(
    trades: List[Trade],
    initial_capital: float,
    n_calendar_hours: Optional[float] = None,
) -> Dict:
    if not trades:
        return {"n": 0, "total_pnl": 0.0}
    pnls = np.array([t.pnl for t in trades], dtype=float)
    n = len(pnls)
    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]
    n_wins = len(wins)
    n_losses = n - n_wins
    win_rate = n_wins / n if n else 0.0
    total_pnl = float(np.sum(pnls))
    gross_w = float(np.sum(wins)) if len(wins) else 0.0
    gross_l = abs(float(np.sum(losses))) if len(losses) else 0.0
    profit_factor = gross_w / gross_l if gross_l > 1e-10 else (float("inf") if gross_w > 0 else 0.0)
    avg_win = float(np.mean(wins)) if len(wins) else 0.0
    avg_loss = abs(float(np.mean(losses))) if len(losses) else 0.0
    expectancy = float(np.mean(pnls))
    std_pnl = float(np.std(pnls, ddof=1)) if n > 1 else 0.0

    # Equity curve
    equity = np.cumsum(np.concatenate([[initial_capital], pnls]))
    peak = np.maximum.accumulate(equity)
    dd_arr = np.zeros_like(equity)
    mask = peak > 0
    dd_arr[mask] = (peak[mask] - equity[mask]) / peak[mask] * 100.0
    max_dd_pct = float(np.max(dd_arr))
    max_dd_idx = int(np.argmax(dd_arr))
    max_dd_dollar = float(dd_arr[max_dd_idx] * peak[max_dd_idx] / 100.0)

    # Returns per trade
    ret = pnls / initial_capital
    mean_ret = float(np.mean(ret))
    std_ret = float(np.std(ret, ddof=1)) if n > 1 else 1e-10

    if n_calendar_hours and n_calendar_hours > 0:
        scale = math.sqrt(8760.0 / n_calendar_hours)
    else:
        scale = math.sqrt(n)
    sharpe = (mean_ret / std_ret) * scale if std_ret > 1e-10 else 0.0
    neg_ret = ret[ret < 0]
    downside_std = float(np.std(neg_ret, ddof=1)) if len(neg_ret) > 1 else 1e-10
    sortino = (mean_ret / downside_std) * scale if downside_std > 1e-10 else 0.0
    calmar = total_pnl / max_dd_dollar if max_dd_dollar > 1e-10 else (float("inf") if total_pnl > 0 else 0.0)

    # Skew / kurt
    if n > 2 and std_ret > 1e-10:
        z = (ret - mean_ret) / std_ret
        skewness = float(np.mean(z ** 3))
        kurtosis = float(np.mean(z ** 4) - 3)
    else:
        skewness, kurtosis = 0.0, 0.0

    # PSR (Probabilistic Sharpe Ratio) approximation
    if abs(sharpe) > 1e-10 and n > 2:
        adj = sharpe * (1 + skewness * sharpe / (3 * math.sqrt(n)))
        denom = math.sqrt(max(1e-10, 1 + adj ** 2 / (2 * n)))
        psr = 0.5 * (1 + math.erf(adj / (denom * math.sqrt(2))))
    else:
        psr = 0.5

    # Start-of-day to trough drawdown
    daily_start: Dict[str, float] = {}
    for i, t in enumerate(trades):
        day = _to_daily_ts(t.entry_time)
        if day not in daily_start:
            daily_start[day] = equity[i]
    sodd_dd = 0.0
    for i in range(1, len(equity)):
        day = _to_daily_ts(trades[i - 1].entry_time)
        start_eq = daily_start.get(day, initial_capital)
        if start_eq > 0:
            dd = (start_eq - equity[i]) / start_eq * 100.0
            if dd > sodd_dd:
                sodd_dd = dd

    pctiles = [5, 25, 50, 75, 95]
    return {
        "n": n,
        "n_wins": n_wins,
        "n_losses": n_losses,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "total_pnl": total_pnl,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "expectancy": expectancy,
        "avg_trade_pnl": expectancy,
        "std_trade_pnl": std_pnl,
        "min_trade": float(np.min(pnls)),
        "max_trade": float(np.max(pnls)),
        "max_dd_pct": max_dd_pct,
        "max_dd_dollar": max_dd_dollar,
        "peak_to_trough_dd_pct": max_dd_pct,
        "start_of_day_to_trough_dd_pct": sodd_dd,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "psr": psr,
        "skewness": skewness,
        "kurtosis": kurtosis,
        "pnl_percentiles": {p: float(np.percentile(pnls, p)) for p in pctiles},
    }


def save_trades(trades: List[Trade], path: str):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "market_id", "strategy", "side", "entry_time", "entry_price",
            "shares", "exit_time", "exit_price", "fee_paid", "pnl", "reason"
        ])
        for t in trades:
            writer.writerow([
                t.market_id, t.strategy, t.side, t.entry_time, f"{t.entry_price:.6f}",
                t.shares, t.exit_time, f"{t.exit_price:.6f}", f"{t.fee_paid:.6f}",
                f"{t.pnl:.6f}", t.reason
            ])


def save_metrics(metrics: Dict, path: str):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(metrics, f, indent=2, default=str)
