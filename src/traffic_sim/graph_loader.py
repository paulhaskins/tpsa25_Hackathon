from __future__ import annotations

from typing import Iterable, Tuple
import random

import networkx as nx


def load_osm(place: str) -> nx.DiGraph:
    """Load a directed street graph from OSM for a given place.

    Falls back to raising on failure; callers can catch and build synthetic.
    Adds edge attributes: length (m) and travel_time (sec). Returns a simple
    DiGraph (non-multi) for demo purposes.
    """
    try:
        import osmnx as ox  # type: ignore

        G = ox.graph_from_place(place, network_type="drive", simplify=True)
        G = ox.add_edge_lengths(G)
        G = ox.add_edge_speeds(G)
        G = ox.add_edge_travel_times(G)
        # Convert to DiGraph without multiedges: pick shortest-time per (u,v)
        DG = nx.DiGraph()
        for n, data in G.nodes(data=True):
            DG.add_node(n, **{k: data.get(k) for k in ("x", "y")})
        for u, v, data in G.edges(data=True):
            length = float(data.get("length", 1.0))
            speed_kph = float(data.get("speed_kph", 30.0))
            travel_time = float(data.get("travel_time", length / (speed_kph * 1000 / 3600)))
            if DG.has_edge(u, v):
                if travel_time < DG[u][v]["travel_time"]:
                    DG[u][v].update({
                        "length": length,
                        "speed_kph": speed_kph,
                        "travel_time": travel_time,
                    })
            else:
                DG.add_edge(u, v, length=length, speed_kph=speed_kph, travel_time=travel_time)
        return DG
    except Exception as exc:  # pragma: no cover - exercised via fallback
        raise RuntimeError(f"OSM load failed for {place}: {exc}")


def make_synthetic(n: int = 5, seed: int = 0) -> nx.DiGraph:
    """Create a small n x n grid directed graph with coordinates.

    Nodes have (x,y) roughly like lon/lat but in arbitrary units suitable for
    folium. Edges are bi-directional with length and nominal speeds.
    """
    random.seed(seed)
    G = nx.DiGraph()
    spacing = 0.001
    # Create grid nodes with (x,y)
    for i in range(n):
        for j in range(n):
            node_id = i * n + j
            G.add_node(node_id, x=-6.26 + j * spacing, y=53.34 + i * spacing, type="junction")
    # Add edges in 4-neighborhood with symmetric attributes
    def add_edge(u: int, v: int) -> None:
        length_m = 120.0
        speed_kph = 30.0
        travel_time = length_m / (speed_kph * 1000 / 3600)
        G.add_edge(u, v, length=length_m, speed_kph=speed_kph, travel_time=travel_time)

    for i in range(n):
        for j in range(n):
            u = i * n + j
            if j + 1 < n:
                v = i * n + (j + 1)
                add_edge(u, v)
                add_edge(v, u)
            if i + 1 < n:
                v = (i + 1) * n + j
                add_edge(u, v)
                add_edge(v, u)
    return G


def tag_supernodes(G: nx.DiGraph, n_residential: int, n_sinks: int, seed: int = 0) -> Tuple[Iterable[int], Iterable[int]]:
    """Randomly tag nodes as residential and sink supernodes.

    Sets node attribute "type" in {"residential","sink","junction"} and
    adds simple capacities: residential stores population weight "H" and sink
    capacity/attractiveness "W". Returns the selected node id iterables.
    """
    random.seed(seed)
    nodes = list(G.nodes())
    random.shuffle(nodes)
    res_nodes = nodes[: max(0, n_residential)]
    sink_nodes = nodes[max(0, n_residential) : max(0, n_residential + n_sinks)]
    for n in G.nodes():
        G.nodes[n].setdefault("type", "junction")
        G.nodes[n]["buffer"] = 0.0
    for n in res_nodes:
        G.nodes[n]["type"] = "residential"
        G.nodes[n]["H"] = float(random.randint(50, 200))  # population weight
    for n in sink_nodes:
        G.nodes[n]["type"] = "sink"
        G.nodes[n]["W"] = float(random.randint(50, 200))  # capacity weight
        G.nodes[n]["category"] = random.choice(["work", "park", "retail"])  # grouping
    return res_nodes, sink_nodes


