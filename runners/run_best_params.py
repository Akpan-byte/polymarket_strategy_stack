"""Pick best params from a comprehensive sweep and run them across all sizings."""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.backtest import Signal, Trade, run_strategy as run_strategy_py
from engine.market import load_cached_markets, load_markets, cache_markets
from engine.metrics import compute_metrics, save_metrics, save_trades
from engine.sizing import DEFAULT_SIZINGS

_MARKETS = None


def import_strategy(module_path: str, class_name: str, params: dict = None):
    spec = importlib.util.spec_from_file_location("mod", module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cls = getattr(mod, class_name)
    if params:
        return cls(**params)
    return cls()


def discover_class(module_path: str) -> str:
    spec = importlib.util.spec_from_file_location("mod", module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for n in dir(mod):
        o = getattr(mod, n)
        if isinstance(o, type) and n.startswith("S") and "Strategy" not in n:
            return n
    raise ValueError(f"No strategy class in {module_path}")


def run_one(args_tuple):
    module_path, class_name, params, sizing_key, data_dir, cache_path, out_dir = args_tuple
    strategy = import_strategy(module_path, class_name, params)
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

    try:
        from runners.run_strategy import run_strategy_rust
        trades = run_strategy_rust(strategy, markets, sizing, sizing.initial_balance)
    except Exception as e:
        print(f"Rust failed ({e}), fallback Python for {strategy.name} {sizing_key}")
        trades = run_strategy_py(strategy, markets, sizing, sizing.initial_balance)

    if markets:
        n_hours = (markets[-1].end_ts - markets[0].start_ts) / 3600.0
    else:
        n_hours = None
    metrics = compute_metrics(trades, sizing.initial_balance, n_hours)
    label = f"{strategy.name}_bestparams_{sizing_key}"
    od = Path(out_dir) / label
    od.mkdir(parents=True, exist_ok=True)
    save_trades(trades, str(od / "trades.csv"))
    save_metrics(metrics, str(od / "metrics.json"))
    return label, metrics, params, sizing_key


def pick_best_params(sweep_results: List[dict], min_trades: int = 20) -> Tuple[dict, dict]:
    """Return (best_params, best_metrics) from a list of sweep results for one strategy."""
    candidates = [r for r in sweep_results if r.get("metrics", {}).get("n", 0) >= min_trades]
    if not candidates:
        candidates = sweep_results
    # Score: total_pnl, but strongly penalize ruinous drawdowns
    def score(r):
        m = r.get("metrics", {})
        pnl = m.get("total_pnl", -float("inf"))
        dd = m.get("max_dd_pct", 0)
        n = m.get("n", 0)
        if dd >= 90:  # blown up
            return -float("inf")
        return pnl - 0.5 * dd + 0.01 * n

    best = max(candidates, key=score)
    return best["params"], best["metrics"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sweep-summary", required=True, help="Path to sweep_all_summary.json")
    parser.add_argument("--data", required=True)
    parser.add_argument("--cache", default="")
    parser.add_argument("--strategies-dir", default="strategies")
    parser.add_argument("--sizings", default="s1_fixed_200,s2_pctmin_200,s3_pctmin_150,s4_kelly_quarter_200")
    parser.add_argument("--out-dir", default="results_bestparams")
    parser.add_argument("--min-trades", type=int, default=20)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    with open(args.sweep_summary) as f:
        all_results = json.load(f)

    # Group by strategy name (strip sizing suffix from label)
    by_strategy: Dict[str, List[dict]] = {}
    for r in all_results:
        label = r.get("label", "")
        # label format: <strategy_name>_<sizing>_<paramlabel>
        parts = label.split("_")
        if len(parts) >= 2 and parts[-2].startswith("s") and parts[-1] in ["200", "150"]:
            name = "_".join(parts[:-2])
        else:
            name = parts[0]
        by_strategy.setdefault(name, []).append(r)

    # Pick best params per strategy
    best_params_by_strategy: Dict[str, dict] = {}
    strategy_module_map = {}
    for fp in sorted(Path(args.strategies_dir).glob("s*.py")):
        cls_name = discover_class(str(fp))
        strategy = import_strategy(str(fp), cls_name)
        strategy_module_map[strategy.name] = str(fp)

    for name, results in by_strategy.items():
        params, metrics = pick_best_params(results, args.min_trades)
        best_params_by_strategy[name] = params
        print(f"Best params for {name}: PnL=${metrics.get('total_pnl',0):.2f} n={metrics.get('n',0)} params={params}")

    # Load markets once
    global _MARKETS
    if args.cache and os.path.exists(args.cache):
        print("Loading cache...")
        _MARKETS = load_cached_markets(args.cache)
        print(f"Loaded {len(_MARKETS)} markets")
    elif not args.cache:
        print("Loading markets...")
        _MARKETS = load_markets(args.data)
        print(f"Loaded {len(_MARKETS)} markets")

    sizings = [s.strip() for s in args.sizings.split(",")]
    tasks = []
    for name, params in best_params_by_strategy.items():
        mod_path = strategy_module_map.get(name)
        if not mod_path:
            print(f"No module found for {name}; skipping")
            continue
        cls_name = discover_class(mod_path)
        for sk in sizings:
            tasks.append((mod_path, cls_name, params, sk, args.data, args.cache, args.out_dir))

    print(f"Running {len(tasks)} best-param configs with {args.workers} workers")

    summary: Dict[str, dict] = {}
    import multiprocessing as mp
    mp.set_start_method("fork", force=True)
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for future in as_completed([ex.submit(run_one, t) for t in tasks]):
            label, metrics, params, sizing_key = future.result()
            summary[label] = metrics
            print(f"[{label}] n={metrics.get('n',0)} pnl=${metrics.get('total_pnl',0):.2f} wr={metrics.get('win_rate',0)*100:.1f}% sharpe={metrics.get('sharpe',0):.3f} dd={metrics.get('max_dd_pct',0):.1f}%")

    summary_path = Path(args.out_dir) / "summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\nBest-params run complete. Summary: {summary_path}")


if __name__ == "__main__":
    main()
