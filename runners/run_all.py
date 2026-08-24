"""Discover and run all strategies in parallel, streaming results."""
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


def discover_strategies(strategies_dir: str) -> List[Tuple[str, str]]:
    """Return list of (module_path, class_name) for concrete strategies."""
    out: List[Tuple[str, str]] = []
    p = Path(strategies_dir)
    for fp in sorted(p.glob("s*.py")):
        # Extract class name: assume one Strategy subclass per file named S*Strategy
        text = fp.read_text()
        for line in text.splitlines():
            if line.startswith("class ") and "Strategy" in line:
                name = line.split("class ")[1].split("(")[0].strip()
                out.append((str(fp), name))
                break
    return out


def run_one(args_tuple):
    module_path, class_name, data_dir, cache_path, sizing_key, out_dir, max_files = args_tuple
    import importlib.util
    spec = importlib.util.spec_from_file_location("mod", module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cls = getattr(mod, class_name)
    strategy = cls()
    sizing = DEFAULT_SIZINGS[sizing_key]

    global _MARKETS
    markets = _MARKETS
    if markets is None:
        if cache_path and os.path.exists(cache_path):
            from engine.market import load_cached_markets
            markets = load_cached_markets(cache_path)
        else:
            from engine.market import load_markets
            markets = load_markets(data_dir, max_files=max_files or None)

    trades = run_strategy(strategy, markets, sizing, sizing.initial_balance)
    if markets:
        n_hours = (markets[-1].end_ts - markets[0].start_ts) / 3600.0
    else:
        n_hours = None
    from engine.metrics import compute_metrics
    metrics = compute_metrics(trades, sizing.initial_balance, n_hours)
    label = f"{strategy.name}_{sizing_key}"
    od = Path(out_dir) / label
    od.mkdir(parents=True, exist_ok=True)
    save_trades(trades, str(od / "trades.csv"))
    save_metrics(metrics, str(od / "metrics.json"))
    return label, metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--cache", default="")
    parser.add_argument("--strategies-dir", default="strategies")
    parser.add_argument("--sizings", default="s1_fixed_200,s2_pctmin_200,s3_pctmin_150")
    parser.add_argument("--out-dir", default="results")
    parser.add_argument("--max-files", type=int, default=0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    strategies = discover_strategies(args.strategies_dir)
    print(f"Discovered {len(strategies)} strategies")

    if args.cache and not os.path.exists(args.cache):
        print("Building cache...")
        markets = load_markets(args.data, max_files=args.max_files or None)
        cache_markets(markets, args.cache)
        print(f"Cached {len(markets)} markets")

    # Load markets once in parent; workers inherit via fork (COW) to avoid reloading 4GB cache per worker
    global _MARKETS
    if args.cache and os.path.exists(args.cache):
        print("Loading cache...")
        _MARKETS = load_cached_markets(args.cache)
        print(f"Loaded {len(_MARKETS)} markets from cache")
    elif not args.cache:
        print("Loading markets...")
        _MARKETS = load_markets(args.data, max_files=args.max_files or None)
        print(f"Loaded {len(_MARKETS)} markets")

    sizings = [s.strip() for s in args.sizings.split(",")]
    tasks = []
    for mod, cls in strategies:
        for sk in sizings:
            tasks.append((mod, cls, args.data, args.cache, sk, args.out_dir, args.max_files))

    summary: Dict[str, Dict] = {}
    t0 = time.time()

    import multiprocessing as mp
    mp.set_start_method("fork", force=True)
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for future in as_completed([ex.submit(run_one, t) for t in tasks]):
            label, metrics = future.result()
            summary[label] = metrics
            print(f"[{label}] n={metrics.get('n',0)} pnl=${metrics.get('total_pnl',0):.2f} wr={metrics.get('win_rate',0)*100:.1f}% sharpe={metrics.get('sharpe',0):.3f} dd={metrics.get('max_dd_pct',0):.1f}%")

    elapsed = time.time() - t0
    summary_path = Path(args.out_dir) / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\nAll done in {elapsed:.1f}s. Summary: {summary_path}")


if __name__ == "__main__":
    main()
