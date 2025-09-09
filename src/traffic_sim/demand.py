from __future__ import annotations

from typing import Dict, Iterable
import math
import datetime as dt

import networkx as nx


def is_weekend(t: dt.datetime) -> bool:
    return t.weekday() >= 5


def is_holiday(_: dt.datetime) -> bool:
    # Stub for demo; can be extended to check calendars
    return False


def build_schedules(config: Dict) -> Dict[str, Dict[int, float]]:
    """Build simple per-hour attractiveness for categories.

    Returns mapping category -> {hour -> weight} for 0..23.
    - work peaks 8-10 and 17-18 on weekdays
    - park higher on weekends midday
    - retail moderate afternoons/evenings
    """
    work = {h: 0.2 for h in range(24)}
    for h in range(7, 11):
        work[h] = 1.0
    for h in range(16, 19):
        work[h] = 0.7

    park = {h: 0.2 for h in range(24)}
    for h in range(10, 17):
        park[h] = 0.8

    retail = {h: 0.3 for h in range(24)}
    for h in range(12, 21):
        retail[h] = 0.6

    return {"work": work, "park": park, "retail": retail}


def _hourly_profile(hour: int, weekend: bool) -> float:
    # Morning peak on weekdays; midday peak on weekends
    if weekend:
        return math.exp(-((hour - 13) ** 2) / (2 * 3.0 ** 2))
    return math.exp(-((hour - 8) ** 2) / (2 * 2.0 ** 2))


def inject_sources(G: nx.DiGraph, t: dt.datetime, schedules: Dict[str, Dict[int, float]]) -> None:
    """Inject vehicles from residential nodes into node buffers.

    Vehicles are added to node attribute "buffer" which will be pushed to
    outgoing edges during the simulation step constrained by downstream
    capacities. Total injected at node scales with H and a time profile.
    """
    weekend = is_weekend(t) or is_holiday(t)
    for n, data in G.nodes(data=True):
        if data.get("type") != "residential":
            continue
        H = float(data.get("H", 100.0))
        profile = _hourly_profile(t.hour, weekend)
        # Weak coupling to destination categories; increase when work is strong
        work_w = schedules["work"].get(t.hour, 0.0)
        park_w = schedules["park"].get(t.hour, 0.0)
        retail_w = schedules["retail"].get(t.hour, 0.0)
        demand_scale = 0.5 + 0.5 * (0.6 * work_w + 0.2 * park_w + 0.2 * retail_w)
        arrivals = 0.02 * H * profile * demand_scale
        # update node buffer and metrics
        data["buffer"] = float(data.get("buffer", 0.0)) + float(arrivals)
        data["last_injected"] = float(arrivals)
        data["cum_injected"] = float(data.get("cum_injected", 0.0)) + float(arrivals)


