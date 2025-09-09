"""Neighbourhood detection and collapsing into supernodes.

We detect subgraphs attached to the rest of the network via exactly one
undirected cut-edge (bridge). Each such subgraph is collapsed into a single
"supernode" and edges are rewired accordingly. The supernode stores a 24-point
"external_flow_series" summarising flow across the cut-edge over a day.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import networkx as nx
import numpy as np


def _mean_coord(G: nx.MultiDiGraph, nodes: Iterable[Any]) -> Tuple[float, float]:
    xs: List[float] = []
    ys: List[float] = []
    for n in nodes:
        d = G.nodes[n]
        if "x" in d and "y" in d:
            xs.append(float(d["x"]))
            ys.append(float(d["y"]))
    if not xs or not ys:
        return 0.0, 0.0
    return float(np.mean(xs)), float(np.mean(ys))


def _sum_crossing_flow_series(G: nx.MultiDiGraph, inside: Set[Any], outside: Set[Any]) -> List[float]:
    series = np.zeros(24, dtype=float)
    # Sum flows across boundary in both directions
    for u in inside:
        for v in G.successors(u):
            if v in outside:
                for k in G[u][v]:
                    s = G[u][v][k].get("flow_series")
                    if s is not None:
                        series[: len(s)] += np.array(s[:24], dtype=float)
    for u in outside:
        for v in G.successors(u):
            if v in inside:
                for k in G[u][v]:
                    s = G[u][v][k].get("flow_series")
                    if s is not None:
                        series[: len(s)] += np.array(s[:24], dtype=float)
    return series.tolist()


def detect_single_connection_neighborhoods(G: nx.MultiDiGraph) -> List[Set[Any]]:
    """Detect node sets attached via a single undirected bridge.

    Returns a list of disjoint node sets (neighbourhoods) selected as the
    smaller side of each bridge, skipping overlaps.
    """
    H = nx.Graph(G)  # undirected simple view for bridges
    neighborhoods: List[Set[Any]] = []
    assigned: Set[Any] = set()

    for a, b in nx.bridges(H):
        # Remove bridge and get connected components
        H2 = H.copy()
        if H2.has_edge(a, b):
            H2.remove_edge(a, b)
        comps = list(nx.connected_components(H2))
        # Identify the two sides containing a and b
        side_a = next((c for c in comps if a in c), set())
        side_b = next((c for c in comps if b in c), set())
        if not side_a or not side_b:
            continue
        # Pick smaller side and ensure >1 node
        cand = side_a if len(side_a) <= len(side_b) else side_b
        if len(cand) <= 1:
            continue
        # Skip overlapping with previously chosen neighborhoods
        if any(n in assigned for n in cand):
            continue
        neighborhoods.append(set(cand))
        assigned.update(cand)
    return neighborhoods


def collapse_neighborhoods_to_supernodes(G: nx.MultiDiGraph, neighborhoods: List[Set[Any]]) -> nx.MultiDiGraph:
    """Collapse given neighborhoods into supernodes and rewire edges.

    - Internal edges within a neighborhood are removed.
    - Edges crossing the boundary are rewired to/from the new supernode.
    - Supernode attributes: is_supernode=True, members=list, x/y (mean),
      external_flow_series (24-length list).
    """
    G2: nx.MultiDiGraph = G.copy()
    used_ids: Set[Any] = set(G2.nodes)

    def new_supernode_id(i: int) -> str:
        nid = f"super_{i}"
        while nid in used_ids:
            i += 1
            nid = f"super_{i}"
        used_ids.add(nid)
        return nid

    for idx, group in enumerate(neighborhoods):
        # Determine outside node set
        group_set = set(group)
        outside = set(G2.nodes) - group_set
        if not outside:
            continue

        # Compute mean coordinates and external flow series
        mx, my = _mean_coord(G2, group_set)
        flow_series = _sum_crossing_flow_series(G2, group_set, outside)

        super_id = new_supernode_id(idx)
        G2.add_node(super_id, is_supernode=True, members=sorted(group_set), x=mx, y=my, lat=my, lon=mx, external_flow_series=flow_series)

        # Rewire edges crossing boundary
        # Collect edges to move to avoid mutating while iterating
        to_add: List[Tuple[Any, Any, Dict[str, Any]]] = []
        to_remove: List[Tuple[Any, Any, int]] = []

        for u in group_set:
            for v in list(G2.successors(u)):
                for k, edata in list(G2[u][v].items()):
                    if v in group_set:
                        # internal, remove
                        to_remove.append((u, v, k))
                    else:
                        # boundary out edge: move to (super, v)
                        to_remove.append((u, v, k))
                        to_add.append((super_id, v, edata))
        for u in list(outside):
            for v in list(G2.successors(u)):
                for k, edata in list(G2[u][v].items()):
                    if v in group_set:
                        # boundary in edge: move to (u, super)
                        to_remove.append((u, v, k))
                        to_add.append((u, super_id, edata))

        for u, v, k in to_remove:
            if G2.has_edge(u, v, k):
                G2.remove_edge(u, v, k)
        for u, v, edata in to_add:
            G2.add_edge(u, v, **edata)

        # Remove group nodes
        for n in group_set:
            if n in G2:
                G2.remove_node(n)

    return G2


def detect_and_collapse(G: nx.MultiDiGraph) -> Tuple[nx.MultiDiGraph, List[Set[Any]]]:
    """Convenience: detect single-connection neighborhoods and collapse them."""
    neighs = detect_single_connection_neighborhoods(G)
    Gc = collapse_neighborhoods_to_supernodes(G, neighs)
    return Gc, neighs


__all__ = [
    "detect_single_connection_neighborhoods",
    "collapse_neighborhoods_to_supernodes",
    "detect_and_collapse",
]


