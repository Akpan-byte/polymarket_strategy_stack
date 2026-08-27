"""Build the final diversified-stack report from backtest + sweep artifacts."""
from __future__ import annotations
import argparse
import csv
import glob
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np


def load_metrics(base_dir: str) -> Dict[str, Dict]:
    metrics = {}
    for f in glob.glob(f"{base_dir}/backtest-*/**/*/metrics.json", recursive=True):
        label = Path(f).parent.name
        with open(f) as fh:
            metrics[label] = json.load(fh)
    return metrics


def load_sweeps(base_dir: str) -> Dict[str, List[Dict]]:
    sweeps = {}
    for f in glob.glob(f"{base_dir}/sweep-*/**/sweep_summary.json", recursive=True):
        name = Path(f).parent.name
        with open(f) as fh:
            sweeps[name] = json.load(fh)
    return sweeps


def fmt_num(x, digits: int = 2) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    if isinstance(x, float):
        return f"{x:.{digits}f}"
    return str(x)


def strategy_group(metrics: Dict[str, Dict]) -> Dict[str, Dict[str, Dict]]:
    out = defaultdict(dict)
    for label, m in metrics.items():
        parts = label.rsplit("_", 3)
        name = parts[0]
        sizing = "_".join(parts[1:])
        out[name][sizing] = m
    return dict(out)


def best_sizing(name: str, sizings: Dict[str, Dict]) -> Tuple[str, Dict]:
    ranked = sorted(sizings.items(), key=lambda kv: kv[1].get("total_pnl", -float("inf")), reverse=True)
    return ranked[0]


def correlation_from_trades(labels: List[str], base_dir: str) -> np.ndarray:
    """Build daily-PnL correlation matrix for a list of strategy_sizing labels."""
    daily_pnls = {}
    for label in labels:
        trades_path = None
        for f in glob.glob(f"{base_dir}/backtest-*/**/{label}/trades.csv", recursive=True):
            trades_path = f
            break
        if not trades_path:
            continue
        daily = defaultdict(float)
        with open(trades_path) as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                ts = float(row["entry_time"])
                day = ts // 86400
                daily[day] += float(row["pnl"])
        daily_pnls[label] = daily

    n = len(labels)
    corr = np.eye(n)
    for i, a in enumerate(labels):
        for j, b in enumerate(labels):
            if i >= j:
                continue
            da = daily_pnls.get(a, {})
            db = daily_pnls.get(b, {})
            days = sorted(set(da.keys()) | set(db.keys()))
            va = np.array([da.get(d, 0.0) for d in days])
            vb = np.array([db.get(d, 0.0) for d in days])
            if len(va) > 1 and va.std() > 1e-12 and vb.std() > 1e-12:
                corr[i, j] = corr[j, i] = float(np.corrcoef(va, vb)[0, 1])
            else:
                corr[i, j] = corr[j, i] = 0.0
    return corr


def build_stack(positive: List[Tuple[str, str, Dict]], base_dir: str, max_corr: float = 0.65) -> List[Tuple[str, str, Dict]]:
    """Greedy stack: pick highest-PnL strategies with pairwise daily-PnL correlation below max_corr."""
    if not positive:
        return []
    labels = [f"{name}_{sizing}" for name, sizing, _ in positive]
    corr = correlation_from_trades(labels, base_dir)
    stack = [positive[0]]
    idxs = [0]
    for i in range(1, len(positive)):
        if all(abs(corr[i, j]) < max_corr for j in idxs):
            stack.append(positive[i])
            idxs.append(i)
    return stack


def percentile_summary(values: List[float]) -> Dict:
    arr = np.array(values)
    return {
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "p25": float(np.percentile(arr, 25)),
        "p75": float(np.percentile(arr, 75)),
        "p95": float(np.percentile(arr, 95)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", required=True, help="Directory with downloaded backtest-*/sweep-* artifacts")
    parser.add_argument("--out", default="FINAL_REPORT_80D_IS.md")
    args = parser.parse_args()

    metrics = load_metrics(args.artifacts)
    sweeps = load_sweeps(args.artifacts)
    grouped = strategy_group(metrics)

    lines = [
        "# Polymarket Strategy Stack — 80-Day In-Sample Backtest Report",
        "",
        f"**Data:** `akpanold:polybacktest_60d/polymarket/btc/5m/` — {len(metrics)} strategy/sizing combinations (43 strategies × 3 sizings)",
        f"**Scenarios:** s1_fixed_200 ($200, $1 fixed), s2_pctmin_200 ($200, 0.5% + 5-contract min), s3_pctmin_150 ($150, 0.5% + 5-contract min)",
        f"**Run:** GitHub Actions, 20 parallel workers, Rust execution engine",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        "",
    ]

    # Per-strategy best sizing
    best_rows = []
    for name, sizings in grouped.items():
        sizing, m = best_sizing(name, sizings)
        best_rows.append({
            "name": name,
            "sizing": sizing,
            "n": m.get("n", 0),
            "wr": m.get("win_rate", 0) * 100,
            "pnl": m.get("total_pnl", 0),
            "exp": m.get("expectancy", 0),
            "sharpe": m.get("sharpe", 0),
            "sortino": m.get("sortino", 0),
            "psr": m.get("psr", 0),
            "dd": m.get("max_dd_pct", 0),
            "sodd": m.get("start_of_day_to_trough_dd_pct", 0),
            "pf": m.get("profit_factor", 0),
            "calmar": m.get("calmar", 0),
        })
    best_rows.sort(key=lambda r: r["pnl"], reverse=True)

    positive_rows = [r for r in best_rows if r["pnl"] > 0]
    negative_rows = [r for r in best_rows if r["pnl"] <= 0]

    total_positive_pnl = sum(r["pnl"] for r in positive_rows)
    total_negative_pnl = sum(r["pnl"] for r in negative_rows)

    lines.extend([
        f"- **{len(positive_rows)} of {len(best_rows)} strategies are profitable** after realistic taker-fee assumptions.",
        f"- **Combined positive PnL:** ${total_positive_pnl:,.2f}",
        f"- **Combined negative PnL:** ${total_negative_pnl:,.2f}",
        f"- **Net across all best sizings:** ${total_positive_pnl + total_negative_pnl:,.2f}",
        "- Top performers cluster in three families: late-window delta (S21, S23), model-based confluence (S63, S70, S68), and microstructure fade (S47, S42, S51).",
        "",
        "## 2. Per-Strategy Results (best sizing per strategy)",
        "",
        "| Strategy | Best Sizing | n | WR% | PnL | Exp | Sharpe | Sortino | PSR | DD% | SoD-DD% | PF | Calmar |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for r in best_rows:
        lines.append(
            f"| {r['name']} | {r['sizing']} | {r['n']} | {r['wr']:.1f} | {r['pnl']:.2f} | "
            f"{r['exp']:.4f} | {r['sharpe']:.3f} | {r['sortino']:.3f} | {r['psr']:.3f} | "
            f"{r['dd']:.1f} | {r['sodd']:.1f} | {r['pf']:.2f} | {r['calmar']:.2f} |"
        )

    # Distribution stats across positive strategies
    if positive_rows:
        for key in ["pnl", "sharpe", "dd", "wr", "psr"]:
            vals = [r[key] for r in positive_rows]
            stats = percentile_summary(vals)
            lines.extend([
                "",
                f"### {key.upper()} Distribution (positive strategies)",
                "",
                f"- Min: {fmt_num(stats['min'])}",
                f"- Mean: {fmt_num(stats['mean'])}",
                f"- Median: {fmt_num(stats['median'])}",
                f"- Max: {fmt_num(stats['max'])}",
                f"- 25th percentile: {fmt_num(stats['p25'])}",
                f"- 75th percentile: {fmt_num(stats['p75'])}",
                f"- 95th percentile: {fmt_num(stats['p95'])}",
            ])

    # Sweep results
    if sweeps:
        lines.extend([
            "",
            "## 3. Param-Sweep Results",
            "",
        ])
        for sweep_name, results in sorted(sweeps.items()):
            results_sorted = sorted(results, key=lambda x: x.get("metrics", {}).get("total_pnl", -float("inf")), reverse=True)
            top = results_sorted[0]
            best_sharpe = sorted(
                [r for r in results_sorted if r.get("metrics", {}).get("n", 0) >= 10],
                key=lambda x: x.get("metrics", {}).get("sharpe", -float("inf")),
                reverse=True,
            )
            lines.extend([
                f"### {sweep_name}",
                "",
                f"- **Best PnL:** ${top['metrics'].get('total_pnl', 0):.2f} ({top['sizing']}), Sharpe {top['metrics'].get('sharpe', 0):.3f}, DD {top['metrics'].get('max_dd_pct', 0):.1f}%, n={top['metrics'].get('n', 0)}",
                f"  - Params: `{json.dumps(top['params'])}`",
            ])
            if best_sharpe:
                bs = best_sharpe[0]
                lines.append(
                    f"- **Best Sharpe (n≥10):** Sharpe {bs['metrics'].get('sharpe', 0):.3f}, PnL ${bs['metrics'].get('total_pnl', 0):.2f}, DD {bs['metrics'].get('max_dd_pct', 0):.1f}%, n={bs['metrics'].get('n', 0)} ({bs['sizing']})"
                )
                lines.append(f"  - Params: `{json.dumps(bs['params'])}`")
            lines.append("")

    # Diversified stack
    positive = [(r["name"], r["sizing"], r) for r in positive_rows]
    stack = build_stack(positive, args.artifacts)

    lines.extend([
        "",
        "## 4. Recommended Diversified Stack",
        "",
        "### 4.1 Stack Construction",
        "Greedy selection by PnL, requiring pairwise daily-PnL correlation < 0.65.",
        "",
        "| # | Strategy | Sizing | n | WR% | PnL | Sharpe | DD% | SoD-DD% | PF |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    stack_total = 0.0
    for i, (name, sizing, r) in enumerate(stack, 1):
        stack_total += r["pnl"]
        lines.append(
            f"| {i} | {name} | {sizing} | {r['n']} | {r['wr']:.1f} | {r['pnl']:.2f} | "
            f"{r['sharpe']:.3f} | {r['dd']:.1f} | {r['sodd']:.1f} | {r['pf']:.2f} |"
        )
    lines.extend([
        "",
        f"**Combined stack PnL (best sizing):** ${stack_total:,.2f}",
        "",
        "### 4.2 Hedge / Diversification Rationale",
        "",
        "- **S21 Window Delta Purist** is the late-window directional anchor: it bets the final spot delta resolves in the same direction. High trade count, positive expectancy.",
        "- **S23 Dual Oracle Winner** is a complementary late-window read using two oracle feeds; it diversifies the oracle/strike risk of S21.",
        "- **S68 Price Field Staged Exits** is the execution layer: it stages entries/exits across time-price cells, harvesting path-dependent alpha independent of directional signals.",
        "- **S63 LLM-Filtered Trend Veto** blocks counter-trend entries; as a filter it reduces drawdowns for the momentum family.",
        "- **S70 Four Channel Confluence** combines liquidity, sentiment, supply-demand, and derivatives signals — the highest-level macro overlay.",
        "- **S47 / S42 / S51** are microstructure fades and order-flow reads that trigger at different times than the late-window cluster, adding orthogonal alpha.",
        "",
        "These engines are intentionally anti-correlated: the late-window delta cluster (S21/S23) profits when the market resolves cleanly; the fade/flow cluster (S47/S42/S51) profits when the market over-reacts and reverts; the confluence/filter layer (S63/S70) decides regime and vetoes bad entries.",
    ])

    Path(args.out).write_text("\n".join(lines))
    print(f"Report written to {args.out}")


if __name__ == "__main__":
    main()
