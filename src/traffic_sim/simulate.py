from __future__ import annotations

from typing import Dict, List, Tuple
import datetime as dt

import networkx as nx

from .route import precompute_sink_distances, transition_probs


def _downstream_free_capacity(G: nx.DiGraph, v: int) -> float:
    # Aggregate simple free capacity heuristic: sum of R - r for outgoing edges
    free = 0.0
    for _, w, d in G.out_edges(v, data=True):
        free += max(0.0, float(d.get("R", 0.0)) - float(d.get("r", 0.0)))
    return free


def step(G: nx.DiGraph, t: dt.datetime, params: Dict) -> Dict[str, float]:
    """One simulation step applying simultaneous flows.

    params: {"beta": float, "alpha": float}
    Uses node "buffer" as queued vehicles at nodes. Edge state uses (r,q,R).
    """
    beta = float(params.get("beta", 0.5))
    alpha = float(params.get("alpha", 1.0))

    # Precompute sink distances for routing
    sink_tt = precompute_sink_distances(G)

    # Propose flows for each outgoing edge from node buffers and edge occupancy
    proposed: Dict[Tuple[int, int], float] = {}
    for n in G.nodes():
        probs = transition_probs(G, n, sink_tt, beta=beta, alpha=alpha)
        if not probs:
            continue
        node_buffer = float(G.nodes[n].get("buffer", 0.0))
        # Allow edges to push existing r as well, but keep simple: push from buffer
        total_push = node_buffer
        for (u, v), p in probs.items():
            R_edge = float(G[u][v].get("R", 0.0))
            # limited by edge residual capacity this step
            residual = max(0.0, R_edge - float(G[u][v].get("r", 0.0)))
            flow_uv = min(total_push * p, residual)
            # also clamp by downstream free capacity pool
            free_down = _downstream_free_capacity(G, v)
            if free_down <= 0:
                flow_uv = 0.0
            else:
                flow_uv = min(flow_uv, free_down)
            proposed[(u, v)] = proposed.get((u, v), 0.0) + flow_uv

    # Apply simultaneously: deduct from node buffers, add to edge occupancies
    moved_from_node: Dict[int, float] = {n: 0.0 for n in G.nodes()}
    for (u, v), f in proposed.items():
        if f <= 0:
            continue
        G[u][v]["r"] = float(G[u][v].get("r", 0.0)) + f
        moved_from_node[u] += f
    for n, moved in moved_from_node.items():
        if moved > 0:
            G.nodes[n]["buffer"] = max(0.0, float(G.nodes[n].get("buffer", 0.0)) - moved)

    # Move along edges into head nodes or sinks (one hop per step for demo)
    arrivals = 0.0
    edge_updates: List[Tuple[int, int, float]] = []
    for u, v, d in G.edges(data=True):
        r = float(d.get("r", 0.0))
        if r <= 0:
            continue
        # deliver all r to head node this step (simplified)
        edge_updates.append((u, v, r))
    for u, v, r in edge_updates:
        G[u][v]["r"] = max(0.0, float(G[u][v].get("r", 0.0)) - r)
        if G.nodes[v].get("type") == "sink":
            arrivals += r
            G.nodes[v]["last_arrivals"] = float(r) + float(G.nodes[v].get("last_arrivals", 0.0))
            G.nodes[v]["cum_arrivals"] = float(G.nodes[v].get("cum_arrivals", 0.0)) + float(r)
        else:
            G.nodes[v]["buffer"] = float(G.nodes[v].get("buffer", 0.0)) + r

    total_R = sum(float(d.get("R", 0.0)) for _, _, d in G.edges(data=True))
    total_r = sum(float(d.get("r", 0.0)) for _, _, d in G.edges(data=True))
    saturation = total_r / max(total_R, 1e-6)

    return {"arrivals": arrivals, "saturation": saturation, "total_r": total_r}


def run(G: nx.DiGraph, params: Dict, schedules: Dict, steps: int, start_time: dt.datetime) -> List[Dict[str, float]]:
    """Run multiple steps; caller should inject sources each step before step()."""
    metrics: List[Dict[str, float]] = []
    t = start_time
    for _ in range(steps):
        m = step(G, t, params)
        metrics.append(m)
        t = t + dt.timedelta(minutes=int(params.get("dt_minutes", 60)))
    return metrics


