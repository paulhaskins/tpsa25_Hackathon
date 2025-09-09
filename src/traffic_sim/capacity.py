from __future__ import annotations

from typing import Any

import networkx as nx


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def edge_capacity(G: nx.DiGraph, base_cap: float = 10.0) -> None:
    """Assign per-edge capacity and initialize state.

    For each edge, compute capacity R_i using simple multiplicative factors and
    initialize occupancy r_i and queue q_i to 0.
    """
    for u, v, data in G.edges(data=True):
        length_m = float(data.get("length", 100.0))
        speed_kph = float(data.get("speed_kph", 30.0))
        lanes = float(data.get("lanes", 1.0))
        lanes_factor = lanes if lanes > 0 else 1.0
        speed_factor = _clamp(speed_kph / 50.0, 0.5, 2.0)
        length_factor = _clamp(length_m / 200.0, 0.5, 2.0)
        R = base_cap * lanes_factor * speed_factor * length_factor
        data["R"] = float(R)
        data["r"] = 0.0
        data["q"] = 0.0
        # ensure travel_time present for routing
        if "travel_time" not in data:
            data["travel_time"] = length_m / (max(speed_kph, 1.0) * 1000 / 3600)


