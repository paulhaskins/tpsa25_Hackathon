from __future__ import annotations

from typing import Dict, Tuple

import math
import networkx as nx


def precompute_sink_distances(G: nx.DiGraph, sinks: Tuple[int, ...] | None = None) -> Dict[int, float]:
    """Compute travel time to nearest sink for each node using Dijkstra.

    If sinks is None, autodetect nodes with type == 'sink'.
    Returns a dict node -> best time (seconds). Nodes without a path get inf.
    """
    if sinks is None:
        sinks = tuple(n for n, d in G.nodes(data=True) if d.get("type") == "sink")
    # Reverse graph to run single-source per sink as sink-incoming
    GR = G.reverse(copy=False)
    best: Dict[int, float] = {n: math.inf for n in G.nodes()}
    for s in sinks:
        dist = nx.single_source_dijkstra_path_length(GR, s, weight=lambda u, v, d: float(d.get("travel_time", 1.0)))
        for n, tval in dist.items():
            if tval < best[n]:
                best[n] = float(tval)
    return best


def transition_probs(G: nx.DiGraph, node: int, sink_tt: Dict[int, float], beta: float, alpha: float) -> Dict[tuple[int, int], float]:
    """Compute edge transition probabilities from a node.

    p(u->v) ∝ exp(-beta * ΔTT) * (1 - occ_downstream)^alpha, normalized over
    edges that reduce expected time-to-sink.
    Returns mapping (u,v) -> p. If no improving edges exist, returns empty.
    """
    current_tt = sink_tt.get(node, math.inf)
    candidates: list[tuple[tuple[int, int], float]] = []
    for _, v, data in G.out_edges(node, data=True):
        next_tt = sink_tt.get(v, math.inf)
        if not math.isfinite(next_tt):
            continue
        if next_tt >= current_tt and math.isfinite(current_tt):
            # Only consider edges moving closer, unless current is inf
            if math.isfinite(current_tt):
                continue
        # downstream occupancy fraction. Use r / max(R, epsilon)
        R = float(data.get("R", 1.0))
        r = float(data.get("r", 0.0))
        slack = max(0.0, 1.0 - (r / max(R, 1e-6)))
        delta = max(0.0, next_tt - current_tt)
        weight = math.exp(-beta * delta) * (slack ** max(alpha, 0.0))
        candidates.append(((node, v), weight))
    total = sum(w for _, w in candidates)
    if total <= 0.0:
        return {}
    return {e: w / total for e, w in candidates}


