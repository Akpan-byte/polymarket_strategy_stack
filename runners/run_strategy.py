"""Run a single strategy + sizing and save trades/metrics.

Uses the Rust execution engine when the compiled extension is available,
falling back to the Python engine otherwise."""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.backtest import Signal, Trade, run_strategy as run_strategy_py
from engine.market import load_cached_markets, load_markets, cache_markets
from engine.metrics import compute_metrics, save_metrics, save_trades
from engine.sizing import SizingConfig, DEFAULT_SIZINGS, KellyState, kelly_size
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


def _signal_to_tuple(sig: Signal, shares: int = 0):
    return (
        sig.side,
        int(sig.entry_idx),
        int(sig.exit_idx) if sig.exit_idx is not None else None,
        shares,
    )


def run_strategy_rust(strategy: Strategy, markets, sizing: SizingConfig, initial_balance: float) -> list[Trade]:
    """Run strategy signals through the Rust execution engine."""
    import polybacktest_rs

    sizing_json = json.dumps(asdict(sizing))
    all_trades: list[Trade] = []
    balance = initial_balance
    kelly_state = KellyState()
    use_kelly = sizing.mode == "kelly_quarter"

    for market in markets:
        signals = strategy.generate_signals(market)
        if not signals:
            continue

        signal_tuples = []
        for sig in signals:
            shares = 0
            if use_kelly:
                entry_price = (
                    float(market.best_ask_up[sig.entry_idx])
                    if sig.side == "YES"
                    else float(market.best_ask_down[sig.entry_idx])
                )
                shares = kelly_size(balance, entry_price, sizing, kelly_state)
            signal_tuples.append(_signal_to_tuple(sig, shares))

        rust_trades = polybacktest_rs.run_market(
            market.market_id,
            strategy.name,
            sizing_json,
            balance,
            float(market.start_ts),
            float(market.end_ts),
            float(market.strike),
            market.resolution,
            market.ts,
            market.spot,
            market.price_up,
            market.price_down,
            market.best_ask_up,
            market.best_bid_up,
            market.best_ask_down,
            market.best_bid_down,
            market.rem_sec,
            market.elapsed_sec,
            market.delta_pct,
            signal_tuples,
        )
        for rt in rust_trades:
            t = Trade(**rt)
            all_trades.append(t)
            balance += t.pnl
            if use_kelly:
                kelly_state.update(t.pnl)
            if balance <= 0:
                balance = 0.0
                break
        if balance <= 0:
            break
    return all_trades


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
    parser.add_argument("--force-python", action="store_true", help="Disable Rust engine")
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
    use_rust = not args.force_python
    if use_rust:
        try:
            trades = run_strategy_rust(strategy, markets, sizing, sizing.initial_balance)
            engine = "rust"
        except Exception as e:
            print(f"Rust engine failed ({e}), falling back to Python engine")
            trades = run_strategy_py(strategy, markets, sizing, sizing.initial_balance)
            engine = "python"
    else:
        trades = run_strategy_py(strategy, markets, sizing, sizing.initial_balance)
        engine = "python"
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

    print(f"[{label}] engine={engine} markets={len(markets)} trades={len(trades)} load={load_t:.2f}s backtest={bt_t:.2f}s")
    print(f"  PnL=${metrics.get('total_pnl',0):.2f} WR={metrics.get('win_rate',0)*100:.1f}% Sharpe={metrics.get('sharpe',0):.3f} DD={metrics.get('max_dd_pct',0):.1f}%")


if __name__ == "__main__":
    main()
