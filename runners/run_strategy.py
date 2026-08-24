"""Run a single strategy + sizing and save trades/metrics."""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.backtest import run_strategy
from engine.market import load_cached_markets, load_markets, cache_markets
from engine.metrics import compute_metrics, save_metrics, save_trades
from engine.sizing import SizingConfig, DEFAULT_SIZINGS
from strategies.base import Strategy


def import_strategy(module_path: str, class_name: str, params: dict = None):
    import importlib.util
    spec = importlib.util.spec_from_file_location("mod", module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cls = getattr(mod, class_name)
    if params:
        return cls(**params)
    return cls()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="Directory with .json.gz market files")
    parser.add_argument("--cache", default="", help="Optional cache pickle path")
    parser.add_argument("--strategy-module", required=True)
    parser.add_argument("--strategy-class", required=True)
    parser.add_argument("--params", default="{}", help="JSON dict of strategy params")
    parser.add_argument("--sizing", default="s1_fixed_200", choices=list(DEFAULT_SIZINGS.keys()))
    parser.add_argument("--out-dir", default="results")
    parser.add_argument("--max-files", type=int, default=0)
    args = parser.parse_args()

    t0 = time.time()
    if args.cache and os.path.exists(args.cache):
        markets = load_cached_markets(args.cache)
    else:
        markets = load_markets(args.data, max_files=args.max_files or None)
        if args.cache:
            cache_markets(markets, args.cache)
    load_t = time.time() - t0

    params = json.loads(args.params)
    strategy = import_strategy(args.strategy_module, args.strategy_class, params)
    sizing = DEFAULT_SIZINGS[args.sizing]

    t0 = time.time()
    trades = run_strategy(strategy, markets, sizing, sizing.initial_balance)
    bt_t = time.time() - t0

    # Calendar hours approximated from market timestamps
    if markets:
        n_hours = (markets[-1].end_ts - markets[0].start_ts) / 3600.0
    else:
        n_hours = None
    metrics = compute_metrics(trades, sizing.initial_balance, n_hours)

    label = f"{strategy.name}_{args.sizing}"
    out_dir = Path(args.out_dir) / label
    out_dir.mkdir(parents=True, exist_ok=True)
    save_trades(trades, str(out_dir / "trades.csv"))
    save_metrics(metrics, str(out_dir / "metrics.json"))

    print(f"[{label}] markets={len(markets)} trades={len(trades)} load={load_t:.2f}s backtest={bt_t:.2f}s")
    print(f"  PnL=${metrics.get('total_pnl',0):.2f} WR={metrics.get('win_rate',0)*100:.1f}% Sharpe={metrics.get('sharpe',0):.3f} DD={metrics.get('max_dd_pct',0):.1f}%")


if __name__ == "__main__":
    main()
