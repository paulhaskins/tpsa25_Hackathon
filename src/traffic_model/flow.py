"""Attach time-series flows to nodes or supernodes and project to edges."""

from pathlib import Path
from typing import Dict, Any
import pandas as pd
import networkx as nx


def attach_flows(G: nx.MultiDiGraph, csv_path: Path) -> nx.MultiDiGraph:
    """Attach flows from CSV to nodes as an attribute 'flow_ts'.

    Expected CSV columns: node_id, t0, t1, ... (wide format). Any missing nodes
    are ignored; any missing timestamps are allowed (NaN).
    """
    df = pd.read_csv(csv_path)
    if "node_id" not in df.columns:
        raise ValueError("CSV must contain column 'node_id'")
    flow_cols = [c for c in df.columns if c != "node_id"]
    flows = {
        int(row["node_id"]): {"timestamps": flow_cols, "values": [row[c] for c in flow_cols]}
        for _, row in df.iterrows()
    }
    for n in G.nodes:
        if n in flows:
            G.nodes[n]["flow_ts"] = flows[n]
    return G


def attach_node_flow_series_from_df(G: nx.MultiDiGraph, df: pd.DataFrame) -> nx.MultiDiGraph:
    """Attach per-node time series from a tidy DataFrame.

    Expected df columns:
      - node_id: int or str
      - timestamp index or column (optional)
      - sum_volume or value column; if both sum_volume and avg_volume exist, use sum_volume.

    The function aggregates by node_id and hour (if needed) to produce a 24-length series
    per node under attribute 'node_flow_series'.
    """
    work = df.copy()
    # Identify value column
    value_col = None
    for cand in ["sum_volume", "value", "volume", "count", "avg_volume"]:
        if cand in work.columns:
            value_col = cand
            break
    if value_col is None:
        raise ValueError("DataFrame must contain a volume column (e.g., sum_volume)")

    # Ensure timestamp column exists (from index or a column)
    if work.index.dtype.kind != "M":
        ts_col = None
        for cand in ["timestamp", "time", "End Time", "end_time"]:
            if cand in work.columns:
                ts_col = cand
                break
        if ts_col is None:
            raise ValueError("DataFrame must have a datetime index or a timestamp column")
        work["__ts"] = pd.to_datetime(work[ts_col], errors="coerce", utc=True)
        work = work.set_index("__ts")
    # Group to hourly and by node
    work["hour"] = work.index.hour
    grouped = work.groupby(["node_id", "hour"])[value_col].sum().unstack(fill_value=0.0)
    # Ensure 24 hours
    for h in range(24):
        if h not in grouped.columns:
            grouped[h] = 0.0
    grouped = grouped[sorted(grouped.columns)]

    # Attach to nodes
    for n in G.nodes:
        if n in grouped.index:
            series = grouped.loc[n].astype(float).tolist()
            G.nodes[n]["node_flow_series"] = series
    return G


def project_node_flows_to_edges(G: nx.MultiDiGraph, method: str = "average") -> nx.MultiDiGraph:
    """Create edge 'flow_series' from incident node series.

    method: 'average' (default) averages node_flow_series of u and v.
            'upstream' uses u only; 'downstream' uses v only.
    """
    for u, v, k in G.edges(keys=True):
        su = G.nodes[u].get("node_flow_series")
        sv = G.nodes[v].get("node_flow_series")
        series = None
        if method == "average":
            if su is not None and sv is not None:
                series = [(float(su[i]) + float(sv[i])) / 2.0 for i in range(min(len(su), len(sv), 24))]
            elif su is not None:
                series = su[:24]
            elif sv is not None:
                series = sv[:24]
        elif method == "upstream" and su is not None:
            series = su[:24]
        elif method == "downstream" and sv is not None:
            series = sv[:24]
        if series is not None:
            G.edges[u, v, k]["flow_series"] = [float(x) for x in series]
    return G


