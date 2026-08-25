use numpy::PyReadonlyArray1;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use serde::Deserialize;

/// Sizing configuration mirroring Python engine.sizing.SizingConfig.
#[derive(Debug, Clone, Deserialize)]
struct SizingConfig {
    mode: String,
    initial_balance: f64,
    #[serde(default)]
    fixed_dollar: f64,
    #[serde(default = "default_pct")]
    pct: f64,
    #[serde(default = "default_min_shares")]
    min_shares: i64,
    #[serde(default = "default_fee_multiplier")]
    fee_multiplier: f64,
}

fn default_pct() -> f64 { 0.005 }
fn default_min_shares() -> i64 { 5 }
fn default_fee_multiplier() -> f64 { 0.25 }

impl SizingConfig {
    fn size_trade(&self, balance: f64, entry_price: f64) -> i64 {
        if entry_price <= 0.0 || entry_price >= 1.0 || balance <= 0.0 {
            return 0;
        }
        let dollars = if self.mode == "fixed" {
            self.fixed_dollar
        } else if self.mode == "pct_min" {
            let min_dollars = self.min_shares as f64 * entry_price;
            (self.initial_balance * self.pct).max(min_dollars)
        } else {
            self.fixed_dollar
        };
        let raw = (dollars.min(balance) / entry_price).floor() as i64;
        if raw < self.min_shares {
            return 0;
        }
        (raw / self.min_shares) * self.min_shares
    }
}

fn taker_fee_per_share(price: f64, fee_multiplier: f64) -> f64 {
    if price <= 0.0 || price >= 1.0 {
        0.0
    } else {
        price * fee_multiplier * (price * (1.0 - price)).powi(2)
    }
}

/// Run one market's signals through the execution engine.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn run_market<'py>(
    py: Python<'py>,
    market_id: &str,
    strategy: &str,
    sizing_json: &str,
    initial_balance: f64,
    start_ts: f64,
    end_ts: f64,
    strike: f64,
    resolution: &str,
    ts_arr: PyReadonlyArray1<f64>,
    _spot_arr: PyReadonlyArray1<f64>,
    price_up_arr: PyReadonlyArray1<f64>,
    price_down_arr: PyReadonlyArray1<f64>,
    best_ask_up_arr: PyReadonlyArray1<f64>,
    best_bid_up_arr: PyReadonlyArray1<f64>,
    best_ask_down_arr: PyReadonlyArray1<f64>,
    best_bid_down_arr: PyReadonlyArray1<f64>,
    _rem_sec_arr: PyReadonlyArray1<f64>,
    _elapsed_sec_arr: PyReadonlyArray1<f64>,
    _delta_pct_arr: PyReadonlyArray1<f64>,
    signals: Vec<(String, usize, Option<usize>)>,
) -> PyResult<Vec<Bound<'py, PyDict>>> {
    let sizing: SizingConfig = serde_json::from_str(sizing_json)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("bad sizing json: {e}")))?;

    let n = ts_arr.shape()[0];
    if n == 0 {
        return Ok(Vec::new());
    }

    let ts = ts_arr.as_array();
    let price_up = price_up_arr.as_array();
    let price_down = price_down_arr.as_array();
    let best_ask_up = best_ask_up_arr.as_array();
    let best_bid_up = best_bid_up_arr.as_array();
    let best_ask_down = best_ask_down_arr.as_array();
    let best_bid_down = best_bid_down_arr.as_array();

    let mut trades: Vec<Bound<'py, PyDict>> = Vec::with_capacity(signals.len());
    let mut balance = initial_balance;

    for (side, entry_idx, exit_idx_opt) in signals {
        if entry_idx >= n {
            continue;
        }
        let entry_price = if side == "YES" {
            best_ask_up[entry_idx]
        } else {
            best_ask_down[entry_idx]
        };
        if entry_price.is_nan() || entry_price <= 0.0 || entry_price >= 1.0 {
            continue;
        }

        let shares = sizing.size_trade(balance, entry_price);
        if shares <= 0 {
            continue;
        }
        let entry_cost = shares as f64 * entry_price;
        let entry_fee = shares as f64 * taker_fee_per_share(entry_price, sizing.fee_multiplier);
        if entry_cost + entry_fee > balance {
            continue;
        }

        let (exit_time, exit_price) = if exit_idx_opt.is_none() || exit_idx_opt.unwrap() >= n {
            let ep = if resolution == side { 1.0 } else { 0.0 };
            (end_ts, ep)
        } else {
            let eidx = exit_idx_opt.unwrap();
            let mut ep = if side == "YES" {
                best_bid_up[eidx]
            } else {
                best_bid_down[eidx]
            };
            if ep.is_nan() {
                ep = if side == "YES" { price_up[eidx] } else { price_down[eidx] };
                if ep.is_nan() {
                    ep = if resolution == side { 1.0 } else { 0.0 };
                }
            }
            (ts[eidx], ep)
        };

        let proceeds = shares as f64 * exit_price;
        let pnl = proceeds - entry_cost - entry_fee;
        balance += pnl;
        if balance <= 0.0 {
            balance = 0.0;
        }

        let dict = PyDict::new(py);
        dict.set_item("market_id", market_id)?;
        dict.set_item("strategy", strategy)?;
        dict.set_item("side", &side)?;
        dict.set_item("entry_time", ts[entry_idx])?;
        dict.set_item("entry_price", entry_price)?;
        dict.set_item("shares", shares)?;
        dict.set_item("exit_time", exit_time)?;
        dict.set_item("exit_price", exit_price)?;
        dict.set_item("fee_paid", entry_fee)?;
        dict.set_item("pnl", pnl)?;
        dict.set_item("reason", "rust_engine")?;
        trades.push(dict);

        if balance <= 0.0 {
            break;
        }
    }

    Ok(trades)
}

#[pymodule]
fn polybacktest_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(run_market, m)?)?;
    Ok(())
}
