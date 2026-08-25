"""Strategy 57: Economic-Release Pre-Positioning.

Synthetic macro-release events at fixed UTC hours. Enter early in a market
containing an event, in the direction implied by recent token/spot velocity,
provided the chosen token can be bought <= max_token_price. Exit a fixed
post_exit_sec after the event.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

import numpy as np

from engine.backtest import Signal
from engine.market import Market
from strategies.base import Strategy


class S57EconomicReleasePrepositioning(Strategy):
    name = "S57_Economic_Release_Prepositioning"

    def __init__(
        self,
        event_hours: Tuple[int, ...] = (12, 13, 18, 19),
        post_exit_sec: float = 300.0,
        velocity_window: int = 5,
        min_velocity: float = 0.0,
        max_token_price: float = 0.55,
        max_pre_event_sec: float = 1800.0,
    ):
        self.params = {
            "event_hours": list(event_hours),
            "post_exit_sec": post_exit_sec,
            "velocity_window": velocity_window,
            "min_velocity": min_velocity,
            "max_token_price": max_token_price,
            "max_pre_event_sec": max_pre_event_sec,
        }

    def generate_signals(self, market: Market) -> List[Signal]:
        p = self.params
        n = len(market)
        w = p["velocity_window"]
        if n < max(w, 2) + 1:
            return []

        spot = market.spot
        velocity = np.full(n, np.nan)
        velocity[w:] = (spot[w:] - spot[:-w]) / spot[:-w]

        event_times = self._event_times_in_window(market.start_ts, market.end_ts)
        if not event_times:
            return []

        signals: List[Signal] = []
        for event_ts in event_times:
            event_idx = int(np.searchsorted(market.ts, event_ts, side="left"))
            if event_idx <= 0 or event_idx >= n:
                continue

            # Entry window: from the earliest allowed pre-event time up to (but
            # not including) the event itself.
            entry_start_ts = event_ts - p["max_pre_event_sec"]
            entry_start = max(0, int(np.searchsorted(market.ts, entry_start_ts, side="left")))
            entry_start = max(entry_start, w)

            for idx in range(entry_start, event_idx):
                vel = velocity[idx]
                if np.isnan(vel) or abs(vel) < p["min_velocity"]:
                    continue

                side = "YES" if vel > 0 else "NO"
                ask = market.best_ask_up[idx] if side == "YES" else market.best_ask_down[idx]
                if np.isnan(ask) or ask <= 0 or ask > p["max_token_price"]:
                    continue

                exit_ts = event_ts + p["post_exit_sec"]
                exit_idx = int(np.searchsorted(market.ts, exit_ts, side="left"))
                if exit_idx >= n:
                    exit_idx = None  # hold to resolution

                reason = (
                    f"pre_event vel={vel:+.4%} side={side} "
                    f"ask={ask:.3f} event_utc={datetime.fromtimestamp(event_ts, tz=timezone.utc):%H:%M}"
                )
                signals.append(Signal(side=side, entry_idx=idx, exit_idx=exit_idx, reason=reason))
                break  # one entry per event

        return signals

    def _event_times_in_window(self, start_ts: float, end_ts: float) -> List[float]:
        p = self.params
        start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(end_ts, tz=timezone.utc)
        day = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)

        times: List[float] = []
        while day <= end_dt:
            for hour in p["event_hours"]:
                candidate = day.replace(hour=hour, minute=0, second=0, microsecond=0)
                ts = candidate.timestamp()
                if start_ts <= ts <= end_ts:
                    times.append(ts)
            day += timedelta(days=1)
        return times

    def param_sweep(self):
        p = self.params
        for post_exit in [300.0, 600.0]:
            for vw in [3, 5]:
                for mv in [0.0, 0.0005]:
                    for mtp in [0.50, 0.55]:
                        for mpe in [1800.0, 3600.0]:
                            yield {
                                "event_hours": p["event_hours"],
                                "post_exit_sec": post_exit,
                                "velocity_window": vw,
                                "min_velocity": mv,
                                "max_token_price": mtp,
                                "max_pre_event_sec": mpe,
                            }, f"pe{int(post_exit)}_vw{vw}_mv{mv}_mtp{mtp}_mpe{int(mpe)}"
