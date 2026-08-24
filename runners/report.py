"""Generate a markdown report from a summary.json file."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Dict, List


def fmt(v, digits: int = 3) -> str:
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True, help="summary.json path")
    parser.add_argument("--out", default="report.md")
    args = parser.parse_args()

    with open(args.summary) as f:
        summary: Dict[str, Dict] = json.load(f)

    rows: List[Dict] = []
    for label, m in summary.items():
        rows.append({
            "label": label,
            "n": m.get("n", 0),
            "wr": m.get("win_rate", 0) * 100,
            "pnl": m.get("total_pnl", 0),
            "exp": m.get("expectancy", 0),
            "sharpe": m.get("sharpe", 0),
            "sortino": m.get("sortino", 0),
            "psr": m.get("psr", 0),
            "dd": m.get("max_dd_pct", 0),
            "pf": m.get("profit_factor", 0),
            "calmar": m.get("calmar", 0),
        })

    rows.sort(key=lambda r: r["pnl"], reverse=True)

    lines = [
        "# Polymarket Strategy Stack — Backtest Report",
        "",
        f"Strategies run: {len(rows)}",
        "",
        "## Top Performers",
        "",
        "| Strategy | N | WR% | PnL | Exp | Sharpe | Sortino | PSR | DD% | PF | Calmar |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows[:30]:
        lines.append(
            f"| {r['label']} | {r['n']} | {r['wr']:.1f} | {r['pnl']:.2f} | "
            f"{r['exp']:.3f} | {r['sharpe']:.3f} | {r['sortino']:.3f} | {r['psr']:.3f} | "
            f"{r['dd']:.1f} | {r['pf']:.2f} | {r['calmar']:.2f} |"
        )

    # Distribution of PnL
    pnls = [r["pnl"] for r in rows if r["n"] > 0]
    if pnls:
        lines.extend([
            "",
            "## PnL Distribution (trading strategies only)",
            "",
            f"- Count: {len(pnls)}",
            f"- Mean: {sum(pnls)/len(pnls):.2f}",
            f"- Median: {sorted(pnls)[len(pnls)//2]:.2f}",
            f"- Min: {min(pnls):.2f}",
            f"- Max: {max(pnls):.2f}",
        ])

    lines.append("")
    Path(args.out).write_text("\n".join(lines))
    print(f"Report written to {args.out}")


if __name__ == "__main__":
    main()
