"""Param sweep for a single strategy across all three sizing configs."""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.backtest import run_strategy
from engine.market import load_cached_markets, load_markets, cache_markets
from engine.metrics import compute_metrics, save_metrics, save_trades
from engine.sizing import DEFAULT_SIZINGS

_MARKETS = None


def import_strategy(module_path: str, class_name: str):
    spec = importlib.util.spec_from_file_location("mod", module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, class_name)


def _param_label(params: dict) -> str:
    parts = []
    for k in sorted(params.keys()):
        v = params[k]
        if isinstance(v, float):
            parts.append(f"{k}{v:.4f}")
        elif isinstance(v, dict):
            # Serialize dict compactly without special characters.
            items = sorted(v.items())
            parts.append(f"{k}" + "-".join(f"{kk}{vv}" for kk, vv in items))
        else:
            parts.append(f"{k}{v}")
    label = "_".join(parts)
    # Sanitize characters disallowed in artifact paths across file systems.
    for ch in ['"', ':', '<', '>', '|', '*', '?', '\\', '/', '\n', '\r', ' ']:
        label = label.replace(ch, "")
    return label[:120]


def run_one(args_tuple):
    module_path, class_name, params, sizing_key, data_dir, cache_path, out_dir = args_tuple
    cls = import_strategy(module_path, class_name)
    strategy = cls(**params)
    sizing = DEFAULT_SIZINGS[sizing_key]

    global _MARKETS
    markets = _MARKETS
    if markets is None:
        if cache_path and os.path.exists(cache_path):
            from engine.market import load_cached_markets
            markets = load_cached_markets(cache_path)
        else:
            from engine.market import load_markets
            markets = load_markets(data_dir)

    trades = run_strategy(strategy, markets, sizing, sizing.initial_balance)
    if markets:
        n_hours = (markets[-1].end_ts - markets[0].start_ts) / 3600.0
    else:
        n_hours = None
    metrics = compute_metrics(trades, sizing.initial_balance, n_hours)
    plabel = _param_label(params)
    label = f"{strategy.name}_{sizing_key}_{plabel}"
    od = Path(out_dir) / label
    od.mkdir(parents=True, exist_ok=True)
    save_trades(trades, str(od / "trades.csv"))
    save_metrics(metrics, str(od / "metrics.json"))
    return label, metrics, params, sizing_key


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--cache", default="")
    parser.add_argument("--strategy-module", required=True)
    parser.add_argument("--strategy-class", required=True)
    parser.add_argument("--sizings", default="s1_fixed_200,s2_pctmin_200,s3_pctmin_150")
    parser.add_argument("--out-dir", default="results_sweep")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--max-combos", type=int, default=0, help="Limit total combos per sizing")
    args = parser.parse_args()

    cls = import_strategy(args.strategy_module, args.strategy_class)
    sizings = [s.strip() for s in args.sizings.split(",")]

    if args.cache and not os.path.exists(args.cache):
        print("Building cache...")
        markets = load_markets(args.data)
        cache_markets(markets, args.cache)
        print(f"Cached {len(markets)} markets")

    # Load markets once in parent; workers inherit via fork (COW)
    global _MARKETS
    if args.cache and os.path.exists(args.cache):
        print("Loading cache...")
        _MARKETS = load_cached_markets(args.cache)
        print(f"Loaded {len(_MARKETS)} markets from cache")
    elif not args.cache:
        print("Loading markets...")
        _MARKETS = load_markets(args.data)
        print(f"Loaded {len(_MARKETS)} markets")

    # Build task list from param_sweep
    tasks: List[Tuple] = []
    combo_count = 0
    for params, label in cls().param_sweep():
        for sk in sizings:
            tasks.append((args.strategy_module, args.strategy_class, params, sk, args.data, args.cache, args.out_dir))
            combo_count += 1
            if args.max_combos and combo_count >= args.max_combos:
                break
        if args.max_combos and combo_count >= args.max_combos:
            break

    print(f"Sweeping {combo_count} combos across {len(sizings)} sizings with {args.workers} workers")

    results: List[Dict] = []
    t0 = time.time()

    import multiprocessing as mp
    mp.set_start_method("fork", force=True)
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for future in as_completed([ex.submit(run_one, t) for t in tasks]):
            label, metrics, params, sizing_key = future.result()
            results.append({
                "label": label,
                "sizing": sizing_key,
                "params": params,
                "metrics": metrics,
            })
            print(f"[{label}] n={metrics.get('n',0)} pnl=${metrics.get('total_pnl',0):.2f} sharpe={metrics.get('sharpe',0):.3f} dd={metrics.get('max_dd_pct',0):.1f}%")

    elapsed = time.time() - t0
    # Sort by total_pnl
    results.sort(key=lambda x: x["metrics"].get("total_pnl", -float("inf")), reverse=True)
    summary_path = Path(args.out_dir) / "sweep_summary.json"
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSweep done in {elapsed:.1f}s. Top: {results[0]['label']} PnL=${results[0]['metrics'].get('total_pnl',0):.2f}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
