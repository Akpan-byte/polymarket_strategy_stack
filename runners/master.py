"""Master orchestrator: run all strategies, sweep winners, report, sync."""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def run(cmd: list, cwd: str = ""):
    if not cwd:
        cwd = str(Path(__file__).resolve().parent.parent)
    print("\n>>> " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--cache", default="cache/markets.pkl")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--out-dir", default="results")
    parser.add_argument("--sweep-top-k", type=int, default=5, help="Param-sweep top K strategies")
    parser.add_argument("--sync", action="store_true", help="Sync results/docs to Google Drive")
    args = parser.parse_args()

    # 1. Run all strategies
    run([
        "python3", "runners/run_all.py",
        "--data", args.data,
        "--cache", args.cache,
        "--out-dir", args.out_dir,
        "--workers", str(args.workers),
    ])

    # 2. Identify top strategies by PnL
    summary_path = Path(args.out_dir) / "summary.json"
    with open(summary_path) as f:
        summary = json.load(f)

    trading = [(label, m) for label, m in summary.items() if m.get("n", 0) > 20]
    trading.sort(key=lambda x: x[1].get("total_pnl", -float("inf")), reverse=True)
    top = trading[:args.sweep_top_k]

    # 3. Discover strategies to map names to module/class
    from runners.run_all import discover_strategies
    from engine.sizing import DEFAULT_SIZINGS
    sizing_keys = list(DEFAULT_SIZINGS.keys())
    strat_map = {}
    for mod, cls in discover_strategies("strategies"):
        import importlib.util
        spec = importlib.util.spec_from_file_location("tmp", mod)
        tmp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tmp)
        name = getattr(getattr(tmp, cls), "name", cls)
        strat_map[name] = (mod, cls)

    # 4. Param sweep top strategies
    sweep_count = 0
    for label, m in top:
        name = label
        for sk in sizing_keys:
            if label.endswith(f"_{sk}"):
                name = label[:-len(f"_{sk}")]
                break
        if name not in strat_map:
            print(f"  Cannot map {label} to module; skipping sweep")
            continue
        mod, cls = strat_map[name]
        sweep_dir = f"{args.out_dir}_sweep_{name}"
        run([
            "python3", "runners/sweep.py",
            "--data", args.data,
            "--cache", args.cache,
            "--strategy-module", mod,
            "--strategy-class", cls,
            "--out-dir", sweep_dir,
            "--workers", str(args.workers),
            "--max-combos", "50",
        ])
        sweep_count += 1

    print(f"\nTop {len(top)} strategies to sweep; swept {sweep_count}:")
    for label, m in top:
        print(f"  {label}  PnL=${m.get('total_pnl',0):.2f}  Sharpe={m.get('sharpe',0):.3f}")

    # 5. Generate report
    run([
        "python3", "runners/report.py",
        "--summary", str(summary_path),
        "--out", str(Path(args.out_dir) / "report.md"),
    ])

    # 6. Sync to Drive
    if args.sync:
        run(["python3", "runners/sync_drive.py", "--results", args.out_dir, "--docs", "docs"])

    print("\nMaster run complete.")


if __name__ == "__main__":
    main()
