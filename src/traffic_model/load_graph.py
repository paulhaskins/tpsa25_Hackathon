"""Load a street graph from CSV node and edge tables.

This module reconstructs a NetworkX MultiDiGraph given two CSV files:
  - node_data.csv: one row per node with an id and coordinates
  - edges_data.csv: one row per edge with endpoints (u, v) and attributes

Expected columns (flexible, with fallbacks):
  Nodes:
    - id: "node_id" (preferred), or "id" / "osmid"
    - latitude: "lat" (preferred) or "y" / "latitude"
    - longitude: "lon" (preferred) or "x" / "lng" / "longitude"
    - any other columns will be attached as node attributes

  Edges:
    - endpoints: "u", "v" (preferred). Fallbacks: "src"/"source" and "dst"/"target"
    - key (optional): "key"; if absent, a new parallel edge key is created automatically
    - common attributes if present: "length" (float), "highway" (str), "lanes" (int/str)

Usage:
  from traffic_model.load_graph import load_graph_from_csv
  G = load_graph_from_csv("node_data.csv", "edges_data.csv")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

import pandas as pd
import networkx as nx
import numpy as np


def _first_present(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _infer_node_columns(nodes: pd.DataFrame) -> Tuple[str, str, str]:
    node_id_col = _first_present(nodes, ["node_id", "id", "osmid"])
    if not node_id_col:
        raise ValueError("Nodes CSV is missing an id column (expected one of: node_id, id, osmid)")

    lat_col = _first_present(nodes, ["lat", "y", "latitude"])  # prefer 'lat'
    lon_col = _first_present(nodes, ["lon", "x", "lng", "longitude"])  # prefer 'lon'
    if not lat_col or not lon_col:
        raise ValueError("Nodes CSV must include latitude/longitude columns (lat/lon or equivalents)")
    return node_id_col, lat_col, lon_col


def _infer_edge_columns(edges: pd.DataFrame) -> Tuple[str, str, Optional[str]]:
    u_col = _first_present(edges, ["u", "src", "source"])
    v_col = _first_present(edges, ["v", "dst", "target"])
    if not u_col or not v_col:
        raise ValueError("Edges CSV must include endpoint columns (u/v or source/target)")
    key_col = "key" if "key" in edges.columns else None
    return u_col, v_col, key_col


def _maybe_cast(value: Any, cast_type):
    try:
        return cast_type(value)
    except Exception:
        return value


def _parse_lanes(value: Any) -> int:
    """Parse lanes to an integer; default to 1 if missing/invalid.

    Accepts integers, floats, numeric strings, or composite strings like "2;3".
    For composite strings, returns the maximum numeric part found.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 1
    # Direct conversions
    try:
        iv = int(value)
        if iv > 0:
            return iv
    except Exception:
        pass
    # Try float cast
    try:
        fv = float(str(value).strip())
        if fv > 0:
            return max(1, int(round(fv)))
    except Exception:
        pass
    # Parse composite like "2;3" or "2|3"
    tokens = [t for sep in [";", "|", ",", "/", ":", "-"] for t in str(value).split(sep)]
    numeric: list[float] = []
    for t in tokens:
        try:
            numeric.append(float(t))
        except Exception:
            continue
    if numeric:
        return max(1, int(round(max(numeric))))
    return 1


def load_graph_from_csv(nodes_csv: Path | str, edges_csv: Path | str, edges_out_csv: Optional[Path | str] = None) -> nx.MultiDiGraph:
    """Load node and edge tables and reconstruct a MultiDiGraph.

    Parameters
    ----------
    nodes_csv: Path | str
        Path to node CSV file.
    edges_csv: Path | str
        Path to edge CSV file.

    Returns
    -------
    nx.MultiDiGraph
        The reconstructed directed multigraph with node and edge attributes.
    """
    nodes_path = Path(nodes_csv)
    edges_path = Path(edges_csv)

    nodes_df = pd.read_csv(nodes_path)
    edges_df = pd.read_csv(edges_path)

    node_id_col, lat_col, lon_col = _infer_node_columns(nodes_df)
    u_col, v_col, key_col = _infer_edge_columns(edges_df)

    G = nx.MultiDiGraph()

    # Add nodes with attributes; normalise to x=lon, y=lat as in OSMnx
    for _, row in nodes_df.iterrows():
        node_id = row[node_id_col]
        # Ensure hashable ids (int where possible)
        try:
            node_id = int(node_id)
        except Exception:
            pass

        lat = float(row[lat_col])
        lon = float(row[lon_col])
        attrs: Dict[str, Any] = row.to_dict()
        # Normalise coordinate attribute names commonly used by OSMnx
        attrs["y"] = lat
        attrs["x"] = lon
        attrs["lat"] = lat
        attrs["lon"] = lon
        G.add_node(node_id, **attrs)

    # Compute per-edge capacity and add edges with attributes
    capacities: list[int] = []
    for _, row in edges_df.iterrows():
        u = row[u_col]
        v = row[v_col]
        # Cast endpoints to int where possible to match node ids
        try:
            u = int(u)
        except Exception:
            pass
        try:
            v = int(v)
        except Exception:
            pass

        edge_attrs: Dict[str, Any] = row.to_dict()

        # Normalise common attributes if present
        if "length" in edge_attrs:
            edge_attrs["length"] = _maybe_cast(edge_attrs["length"], float)
        # lanes parsing (preserve original, store parsed as lanes_int)
        parsed_lanes = _parse_lanes(edge_attrs.get("lanes", None))
        edge_attrs["lanes_int"] = parsed_lanes
        # capacity in vehicles/hour
        capacity = int(parsed_lanes * 1800)
        edge_attrs["capacity"] = capacity
        capacities.append(capacity)
        if "highway" in edge_attrs and pd.isna(edge_attrs["highway"]):
            edge_attrs["highway"] = None

        if key_col and key_col in row and pd.notna(row[key_col]):
            key = row[key_col]
            try:
                key = int(key)
            except Exception:
                pass
            # Remove key from edge_attrs to avoid duplicate keyword argument
            edge_attrs_copy = edge_attrs.copy()
            edge_attrs_copy.pop(key_col, None)
            G.add_edge(u, v, key=key, **edge_attrs_copy)
        else:
            # Let MultiDiGraph assign a new parallel edge key automatically
            G.add_edge(u, v, **edge_attrs)

    # Save updated edges CSV (with capacity) for inspection
    if capacities:
        out_path = Path(edges_out_csv) if edges_out_csv is not None else edges_path.with_name(edges_path.stem + "_with_capacity.csv")
        edges_out = edges_df.copy()
        edges_out["capacity"] = capacities
        # also include parsed lanes for clarity
        if "lanes" not in edges_out.columns:
            edges_out["lanes"] = [row.get("lanes", None) for _, row in edges_df.iterrows()]
        edges_out["lanes_int"] = [
            _parse_lanes(val) for val in edges_df.get("lanes", pd.Series([None] * len(edges_df)))
        ]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        edges_out.to_csv(out_path, index=False)

    return G


__all__ = ["load_graph_from_csv"]


def generate_synthetic_flows(G: nx.MultiDiGraph, center: Optional[tuple[float, float]] = None, seed: Optional[int] = 42) -> nx.MultiDiGraph:
    """Generate a 24-hour synthetic flow time series for each directed edge.

    Heuristic:
      - Define a city center as the mean (x, y) of all nodes unless provided.
      - Classify each edge as inbound (points toward center) or outbound.
      - Morning peak (07-09): higher on inbound; Evening peak (16-18): higher on outbound.
      - Other hours: moderate values; add small random variation.

    Flows are scaled by edge capacity if available; otherwise assume lanes=1 -> capacity=1800.
    The series is stored as a list of 24 numbers in edge attribute 'flow_series'.
    """
    rng = np.random.default_rng(seed)

    # Determine center (x: lon, y: lat) in graph coords
    if center is None:
        xs = [d.get("x") for _, d in G.nodes(data=True) if d.get("x") is not None]
        ys = [d.get("y") for _, d in G.nodes(data=True) if d.get("y") is not None]
        if not xs or not ys:
            raise ValueError("Graph nodes must have 'x' and 'y' coordinates to generate flows")
        cx, cy = float(np.mean(xs)), float(np.mean(ys))
    else:
        cx, cy = center

    morning_hours = {7, 8, 9}
    evening_hours = {16, 17, 18}

    def classify_inbound(u_xy: tuple[float, float], v_xy: tuple[float, float]) -> bool:
        # Edge direction from u->v, center vector from u->center. If dot>0, edge heads toward center.
        ux, uy = u_xy
        vx, vy = v_xy
        ex, ey = (vx - ux), (vy - uy)
        cxv, cyv = (cx - ux), (cy - uy)
        dot = ex * cxv + ey * cyv
        return dot > 0

    def capacity_for_edge(attrs: Dict[str, Any]) -> int:
        cap = attrs.get("capacity")
        if cap is None:
            lanes = _parse_lanes(attrs.get("lanes"))
            cap = lanes * 1800
        try:
            return int(cap)
        except Exception:
            return 1800

    # Pre-extract node positions for speed
    node_xy: Dict[Any, tuple[float, float]] = {
        n: (d.get("x"), d.get("y")) for n, d in G.nodes(data=True)
        if d.get("x") is not None and d.get("y") is not None
    }

    for u, v, k, attrs in G.edges(keys=True, data=True):
        u_xy = node_xy.get(u)
        v_xy = node_xy.get(v)
        if u_xy is None or v_xy is None:
            # skip if coordinates missing
            continue
        inbound = classify_inbound(u_xy, v_xy)
        cap = capacity_for_edge(attrs)

        series = []
        for h in range(24):
            # Base multipliers
            if h in morning_hours:
                base = 0.80 if inbound else 0.30
            elif h in evening_hours:
                base = 0.30 if inbound else 0.80
            else:
                # Off-peak: moderate; slightly higher in daytime than night
                if 10 <= h <= 15:
                    base = 0.45 if inbound else 0.50
                elif 6 <= h < 10 or 18 < h <= 21:
                    base = 0.35 if inbound else 0.40
                else:
                    base = 0.20

            # Random fluctuation +/- 10%
            fluct = 1.0 + rng.uniform(-0.10, 0.10)
            value = max(0.0, base * cap * fluct)
            series.append(float(value))

        # Store per parallel edge key
        G.edges[u, v, k]["flow_series"] = series

    return G



