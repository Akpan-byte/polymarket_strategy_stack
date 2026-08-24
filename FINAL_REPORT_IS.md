# Polymarket Strategy Stack — In-Sample Backtest Report

**Data:** `~/polybacktest_btc5m/is/` (1,143 BTC 5-min markets, May 8 → Jul 1)  
**Scenarios:** s1_fixed_200 ($200, $1 fixed), s2_pctmin_200 ($200, 0.5% + 5-contract min), s3_pctmin_150 ($150, 0.5% + 5-contract min)  
**Run:** 24 strategies × 3 sizings = 63 jobs on 16 workers, Akpan laptop  
**Generated:** 2026-08-24

---

## 1. Executive Summary

- **21 of 24 strategy modules produced trades.** Three never fired in this IS slice under their default parameters.
- **Only a handful of strategies are profitable after realistic taker-fee assumptions.** The clear winner is the late-window delta model (Strategy 21).
- **Param-sweeping the positive strategies materially improves risk-adjusted returns**, with the best Sharpe-weighted diversified stack producing **Sharpe 3.64, max drawdown 2.26%, total PnL $57.34 (28.7% on $200)**.
- **Many marketed "high win-rate" strategies are destroyed by fees and adverse selection** once a realistic 0.25–0.50% taker cost and 5-contract minimum are applied.

---

## 2. Per-Strategy Results (best sizing per strategy)

| Strategy | Best Sizing | n | Win Rate | Total PnL | Sharpe | Max DD | Profit Factor |
|---|---|---:|---:|---:|---:|---:|---:|
| S21_WindowDelta_Purist | s3_pctmin_150 | 481 | 86.9% | **$77.51** | **1.128** | 7.0% | 4.12 |
| S47_SpotRebound_LagReversion | s2_pctmin_200 | 2 | 50.0% | $18.00 | 5.929* | 0.5% | — |
| S39_Cross_Window_Momentum_Continuation | s2_pctmin_200 | 845 | 66.7% | $17.33 | 0.082 | 26.2% | 1.05 |
| S35_5m_Lead_15m_Entry | s2_pctmin_200 | 84 | 75.0% | $16.79 | 0.846 | 13.8% | 1.69 |
| S23_DualOracle_Winner | s3_pctmin_150 | 93 | 67.7% | $4.57 | 0.231 | 9.3% | 1.18 |
| S32_MOMENTUM_Mode | s2_pctmin_200 | 375 | 66.7% | $2.50 | 0.027 | 19.4% | 1.02 |
| S24_TWAP_Reversal | s1_fixed_200 | 4 | 25.0% | $1.58 | 1.455* | 0.8% | — |
| S31_ALIGNED_Mode | s1_fixed_200 | 1 | 100.0% | $4.10 | 0.000 | 0.0% | — |

\* Sharpe based on very few trades — not reliable.

**Largest losers:**
- S24_TWAP_Reversal (pct sizing): −$199.99, 100% max DD
- S33_MACD_RSI_VWAP_Stack: −$198.98, 99.5% max DD
- S55_RapidProbability_ChangeChase: −$128.42, 85.8% max DD
- S52_Liquidity_Momentum: −$118.53, 79.2% max DD
- S69_Complementary_ExitDiscipline: −$104.79, 70.6% max DD

---

## 3. Param-Sweep Results

Five strategies with positive baseline PnL were swept exhaustively over their documented parameter grids (50 combos each, 3 sizings).

### 3.1 S21_WindowDelta_Purist
- **Best PnL:** $116.24 (s2_pctmin_200), Sharpe 0.967, DD 6.7%, n=408
  - Params: `t_entry=5`, `delta_full=0.0008`, `delta_half=0.00015`, `delta_min=3e-05`
- **Best Sharpe (n>10):** Sharpe 2.815, PnL $53.62, DD 1.4%, n=13 (s1_fixed_200)
  - Params: `t_entry=5`, `delta_full=0.0008`, `delta_half=0.00015`, `delta_min=5e-05`
- **Insight:** Entering at T-5s with a very small minimum delta maximizes PnL; raising the minimum delta filters noise and improves Sharpe at the cost of trade count.

### 3.2 S23_DualOracle_Winner
- **Best PnL:** $40.42 (s3_pctmin_150), Sharpe 2.916, DD 3.7%, n=72
  - Params: `t_start=15`, `t_min=3`, `edge_min=0.03`, `stale_sec=2`, `vol_window=60`
- **Insight:** A 3-second minimum holding, 2-second stale-tick filter, and 3% minimum edge produce the cleanest risk-adjusted return.

### 3.3 S35_5m_Lead_15m_Entry
- **Best PnL:** $32.92 (s2_pctmin_200), Sharpe 1.814, DD 5.4%, n=83
  - Params: `lead_sec=90`, `confirm_sec=30`, `min_lead_move=0.015`, `min_confirm_move=0.003`, `min_delta=0.0003`, `max_price=0.75`
- **Insight:** Requiring a 1.5% lead move and 0.3% confirmation in the 5-min market, with 30s confirmation window, captures the best lead-lag signal while avoiding late entries.

### 3.4 S39_Cross_Window_Momentum_Continuation
- **Best PnL:** $90.17 (s2_pctmin_200), Sharpe 0.888, DD 14.4%, n=404
  - Params: `short_window=3`, `long_window=10`, `continuation_ratio=0.6`, `min_delta=0.0003`, `min_short_vel=0.01`, `min_long_vel=0.015`, `max_price=0.65`
- **Insight:** 60% continuation ratio and a tight 0.65 max entry price balance PnL and drawdown.

### 3.5 S32_MOMENTUM_Mode
- **Best PnL:** $78.35 (s2_pctmin_200), Sharpe 0.360, DD 15.5%, n=904
  - Params: `vel_window=4`, `min_vel=0.01`, `min_delta=0.0002`, `max_price=0.85`, `sustain_ticks=2`
- **Insight:** Very permissive parameters (max_price 0.85, sustain only 2 ticks) maximize raw PnL but create large drawdowns. Tightening to `max_price=0.65, sustain_ticks=4` improves Sharpe to 0.568 with lower DD.

---

## 4. Recommended Diversified Stack

### 4.1 Rationale
The paper argues that the realistic ceiling for a non-colocated, taker-only operation is **8–10 genuinely independent systems**. From the backtests, five profitable, low-correlation engines survive:

1. **S21_WindowDelta_Purist** — late-window spot-delta reversion (high win rate, low DD)
2. **S39_Cross_Window_Momentum_Continuation** — window-to-window trend continuation
3. **S23_DualOracle_Winner** — late-window oracle/CEX edge capture
4. **S35_5m_Lead_15m_Entry** — lead-lag between 5-min and 15-min markets
5. **S32_MOMENTUM_Mode** — intra-window velocity persistence

### 4.2 Cross-Strategy Correlations (market-level PnL)

|  | S21 | S39 | S32 | S23 | S35 |
|---|---:|---:|---:|---:|---:|
| S21 | 1.000 | 0.062 | 0.119 | 0.192 | 0.036 |
| S39 | 0.062 | 1.000 | 0.585 | 0.029 | 0.015 |
| S32 | 0.119 | 0.585 | 1.000 | 0.036 | 0.077 |
| S23 | 0.192 | 0.029 | 0.036 | 1.000 | 0.071 |
| S35 | 0.036 | 0.015 | 0.077 | 0.071 | 1.000 |

The only meaningful correlation is between S39 and S32 (0.585), both momentum engines. They are kept because one is cross-window and the other is intra-window velocity, but position-weighting reduces their combined influence.

### 4.3 Stack Allocation (Sharpe-Weighted)

| Component | Weight | n | PnL | Sharpe | Max DD |
|---|---:|---:|---:|---:|---:|
| S23_DualOracle_Winner | 42.0% | 72 | $40.42 | 2.916 | 3.7% |
| S35_5m_Lead_15m_Entry | 26.1% | 83 | $32.92 | 1.814 | 5.4% |
| S21_WindowDelta_Purist | 13.9% | 408 | $116.24 | 0.967 | 6.7% |
| S39_Cross_Window_Momentum | 12.8% | 404 | $90.17 | 0.888 | 14.4% |
| S32_MOMENTUM_Mode | 5.2% | 904 | $78.35 | 0.360 | 15.5% |

### 4.4 Combined Stack Metrics

| Metric | Value |
|---|---|
| Markets traded | 1,031 |
| Total trades (market entries) | 1,031 |
| Win rate | 73.7% |
| Total PnL | **$57.34** (28.7% on $200) |
| Average trade | $0.056 |
| Sharpe (annualized per-trade) | **3.640** |
| Sortino | **4.733** |
| Calmar | **12.669** |
| Max peak-to-trough drawdown | **2.26%** |
| 5th / 25th / 50th / 75th / 95th percentile PnL | −$0.60 / −$0.12 / $0.06 / $0.30 / $0.62 |

### 4.5 Why This Stack Hedges

- **Regime diversification:** S21 profits when late-window spot-delta reverts; S39/S32 profit when momentum continues; S23 profits on oracle mispricings; S35 profits on cross-tenor crowd lag.
- **Time diversification:** S21 and S23 fire in the final seconds; S35 fires mid-window; S39 fires at window open; S32 fires on velocity spikes throughout.
- **Signal-source diversification:** spot delta (S21), oracle/CEX divergence (S23), cross-tenor lead-lag (S35), window-to-window autocorrelation (S39), tick velocity (S32).
- **Risk control:** Sharpe-weighting automatically cuts exposure to high-drawdown engines (S32, S39) and concentrates capital in the highest risk-adjusted edge (S23, S35).

---

## 5. Key Findings & Warnings

1. **Win rate is not alpha.** S22_EndcycleThreshold had a 97.8% win rate and still lost money because its average loss dwarfed its small wins.
2. **Taker fees and minimum sizing are the killers.** Many strategies that look profitable on paper turn negative once 0.5% sizing and a 5-contract minimum are enforced.
3. **Late-window delta is the strongest single edge in this dataset.** Strategy 21 dominates by Sharpe and PnL.
4. **"Exit discipline" strategies (S66, S69) are not standalone profitable here.** They are position-management layers, not entry signals.
5. **No strategy should be run without correlation checks.** The equal-weight stack had $71.62 PnL but 6.2% DD; Sharpe-weighting dropped PnL to $57.34 but cut DD to 2.26%.
6. **This is in-sample only.** These results select parameters that fit this exact 8-week slice. Any live deployment requires walk-forward validation on the held-out OOS data (`~/polybacktest_btc5m/oos1/`).

---

## 6. Files & Artifacts

- `results_is/summary.json` — per-strategy metrics
- `results_is/report.md` — auto-generated master report
- `results_is_sweep_*/sweep_summary.json` — param-sweep outputs
- `FINAL_REPORT_IS.md` — this document
- All outputs are synced to Google Drive: `polybacktest:results/`

---

## 7. Next Steps

1. **Validate on OOS** (`~/polybacktest_btc5m/oos1/`) using only the recommended stack parameters.
2. **Implement live execution wrappers** for the five stack components with the documented parameters.
3. **Add regime filter (Strategy 64)** to disable S21/S23 in strong-trend regimes and S39/S32 in ranging regimes.
4. **Attach S66 7-trigger exit stack** to every live entry for intra-window risk management.
5. **Run a rolling 50-trade performance monitor** (Strategy 65) to auto-reduce size if live win rate diverges > 8 pp from backtest expectation.
