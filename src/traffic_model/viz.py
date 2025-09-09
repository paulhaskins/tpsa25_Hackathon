"""Folium visualisation utilities for traffic graphs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

import folium
import numpy as np
import networkx as nx
import pandas as pd
from datetime import time as dtime
import pytz


def _graph_center(G: nx.MultiDiGraph) -> Tuple[float, float]:
    xs = [d.get("x") for _, d in G.nodes(data=True) if d.get("x") is not None]
    ys = [d.get("y") for _, d in G.nodes(data=True) if d.get("y") is not None]
    if not xs or not ys:
        return 0.0, 0.0
    return float(np.mean(xs)), float(np.mean(ys))


def _edge_intensity(attrs: Dict[str, Any]) -> float:
    series = attrs.get("flow_series")
    if isinstance(series, (list, tuple)) and len(series) > 0:
        return float(np.mean(series))
    # fallback to capacity if no flows
    cap = attrs.get("capacity")
    if cap is None:
        return 0.0
    try:
        return float(cap) * 0.3
    except Exception:
        return 0.0


def _color_from_value(v: float, vmin: float, vmax: float) -> str:
    """Map value to hex color from green (low) to red (high)."""
    if vmax <= vmin:
        t = 0.0
    else:
        t = max(0.0, min(1.0, (v - vmin) / (vmax - vmin)))
    # green -> yellow -> red
    if t < 0.5:
        # green (0,180,0) to yellow (255,200,0)
        a = t / 0.5
        r = int((1 - a) * 0 + a * 255)
        g = int((1 - a) * 180 + a * 200)
        b = 0
    else:
        # yellow (255,200,0) to red (220,0,0)
        a = (t - 0.5) / 0.5
        r = int((1 - a) * 255 + a * 220)
        g = int((1 - a) * 200 + a * 0)
        b = 0
    return f"#{r:02x}{g:02x}{b:02x}"


DEFAULT_TIME_BINS: Dict[str, Dict[str, str]] = {
    "Morning rush": {"start": "06:30", "end": "09:30"},
    "Day": {"start": "09:30", "end": "16:30"},
    "Evening rush": {"start": "16:30", "end": "19:30"},
    "Night": {"start": "19:30", "end": "06:30"},
}

TZ = pytz.timezone("Europe/Dublin")


def _parse_time_str(t: str) -> dtime:
    hh, mm = t.split(":")
    return dtime(hour=int(hh), minute=int(mm))


def _in_bin(local_t: dtime, start: dtime, end: dtime) -> bool:
    if start <= end:
        return start <= local_t < end
    return local_t >= start or local_t < end


def _ensure_local_time(ts: pd.Series) -> pd.Series:
    if ts.dt.tz is None:
        # Treat naive timestamps as Europe/Dublin local
        return ts.dt.tz_localize(TZ)
    return ts.dt.tz_convert(TZ)


def _resolve_volume_column(df: pd.DataFrame) -> str:
    for c in ["volume", "sum_volume", "avg_volume"]:
        if c in df.columns:
            return c
    raise ValueError("SCATS DataFrame must include a volume column (volume/sum_volume/avg_volume)")


def _build_time_bin_masks(local_times: pd.Series, time_bins: Dict[str, Dict[str, str]]) -> Dict[str, pd.Series]:
    masks: Dict[str, pd.Series] = {}
    parsed: Dict[str, Tuple[dtime, dtime]] = {
        name: (_parse_time_str(cfg["start"]), _parse_time_str(cfg["end"]))
        for name, cfg in time_bins.items()
    }
    lt = local_times.dt.time
    # Build boolean masks per bin
    for name, (st, en) in parsed.items():
        masks[name] = lt.apply(lambda t: _in_bin(t, st, en))
    return masks


def compute_node_stats(scats_df: pd.DataFrame, time_bins: Dict[str, Dict[str, str]] | None = None) -> Dict[Any, Dict[str, Any]]:
    """Compute per-node flow rates by bin and approximate occupation.

    Expects scats_df to contain at least columns: 'node_id' and one of
    'volume' | 'sum_volume' | 'avg_volume', plus a timestamp either as index
    or a 'timestamp' column.
    Returns mapping: node_id -> {"flows": {bin->mean_per_hour}, "occupation": int|None, "member_count": 1}
    """
    if scats_df is None or scats_df.empty:
        return {}

    if "node_id" not in scats_df.columns:
        raise ValueError("compute_node_stats expects a 'node_id' column in scats_df")

    vol_col = _resolve_volume_column(scats_df)
    df = scats_df.copy()
    # Bring timestamp to column
    if "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"], errors="coerce")
    else:
        # assume index
        ts = pd.to_datetime(df.index, errors="coerce")
    df["timestamp"] = ts
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
    # Localize
    df["timestamp_local"] = _ensure_local_time(df["timestamp"])  # type: ignore[arg-type]

    bins = time_bins or DEFAULT_TIME_BINS
    masks = _build_time_bin_masks(df["timestamp_local"], bins)

    # Flows per bin: mean per-hour volume per node
    flows: Dict[Any, Dict[str, float | None]] = {}
    for bin_name, mask in masks.items():
        dfb = df[mask]
        if dfb.empty:
            continue
        grp = dfb.groupby("node_id")[vol_col].mean()
        for node_id, mean_v in grp.items():
            flows.setdefault(node_id, {})[bin_name] = float(mean_v)

    # Occupation (approx): EWMA over last hour(s) per node, fallback to last hour sum
    occ: Dict[Any, Optional[int]] = {}
    decay = 0.15
    for node_id, g in df.groupby("node_id"):
        series = g.sort_values("timestamp_local")[vol_col].astype(float)
        if series.empty:
            occ[node_id] = None
            continue
        # Use EWMA to smooth recent hours
        try:
            ew = series.ewm(alpha=decay).mean().iloc[-1]
            occ[node_id] = int(max(0.0, round(ew)))
        except Exception:
            occ[node_id] = int(max(0.0, round(series.iloc[-1])))

    # Build per-node stats
    stats: Dict[Any, Dict[str, Any]] = {}
    all_nodes = set(df["node_id"].unique())
    for n in all_nodes:
        stats[n] = {
            "flows": {k: (None if n not in flows or k not in flows[n] else flows[n][k]) for k in (bins.keys())},
            "occupation": occ.get(n),
            "member_count": 1,
        }
    return stats


def annotate_graph_with_scats(G: nx.MultiDiGraph, scats_df: pd.DataFrame, time_bins: Dict[str, Dict[str, str]] | None = None) -> None:
    """Annotate supernodes on G with stats derived from SCATS data.

    Mapping priority: node attributes 'junction_id' -> df['junction_id'|'site_id'],
    then 'scats_id', then 'name'. If no mapping possible, those rows are dropped.
    Aggregation: for each supernode, aggregate member nodes' stats.
    Stores: G.nodes[sn]['stats'] = {occupation, flows, member_count}.
    """
    if scats_df is None or scats_df.empty:
        return

    # Prepare dataframe with a 'junction_id' column
    df = scats_df.copy()
    # Normalize id column
    if "junction_id" not in df.columns:
        if "site_id" in df.columns:
            df["junction_id"] = df["site_id"]
        elif "node_id" in df.columns:
            # already mapped; skip mapping stage
            mapped_df = df.copy()
            node_stats = compute_node_stats(mapped_df, time_bins)
            # attach trivial to nodes (member_count will be handled per supernode)
            # Aggregate for supernodes next
        else:
            # No usable id, nothing to do
            return

    # Build attribute lookup tables for mapping
    junction_to_node: Dict[Any, Any] = {}
    attr_maps: Dict[str, Dict[Any, Any]] = {"junction_id": {}, "scats_id": {}, "name": {}}
    for n, d in G.nodes(data=True):
        for key in ("junction_id", "scats_id", "name"):
            if d.get(key) is not None:
                attr_maps[key][d.get(key)] = n

    candidates = ["junction_id", "site_id", "scats_id", "name"]
    id_col = next((c for c in candidates if c in df.columns), None)
    if id_col is None:
        return
    # Map df ids to node_ids using priority order
    def map_row_to_node(val: Any) -> Any:
        if val in attr_maps["junction_id"]:
            return attr_maps["junction_id"][val]
        if val in attr_maps["scats_id"]:
            return attr_maps["scats_id"][val]
        if val in attr_maps["name"]:
            return attr_maps["name"][val]
        return None

    df["node_id"] = df[id_col].apply(map_row_to_node)
    df = df.dropna(subset=["node_id"])  # keep only mapped rows
    if df.empty:
        return

    node_stats = compute_node_stats(df, time_bins)

    # Build supernode membership mapping
    members_by_super: Dict[Any, set] = {}
    for n, d in G.nodes(data=True):
        if d.get("is_supernode"):
            mem = d.get("members")
            if isinstance(mem, (list, tuple, set)) and len(mem) > 0:
                members_by_super[n] = set(mem)
            else:
                # no explicit members; treat the supernode as its own member
                members_by_super[n] = {n}

    # Aggregate stats for each supernode over its member nodes
    for sn, mems in members_by_super.items():
        flows_acc: Dict[str, float] = {}
        flows_cnt: Dict[str, int] = {}
        occ_sum = 0
        occ_cnt = 0
        for m in mems:
            st = node_stats.get(m)
            if not st:
                continue
            fdict = st.get("flows", {})
            for bn, val in fdict.items():
                if val is None:
                    continue
                flows_acc[bn] = flows_acc.get(bn, 0.0) + float(val)
                flows_cnt[bn] = flows_cnt.get(bn, 0) + 1
            occ_v = st.get("occupation")
            if isinstance(occ_v, (int, float)):
                occ_sum += int(occ_v)
                occ_cnt += 1
        # Mean per-hour across members
        bins = list((time_bins or DEFAULT_TIME_BINS).keys())
        agg_flows: Dict[str, Optional[float]] = {}
        for bn in bins:
            if flows_cnt.get(bn, 0) > 0:
                agg_flows[bn] = flows_acc.get(bn, 0.0)
            else:
                agg_flows[bn] = None
        occupation = (occ_sum if occ_cnt > 0 else None)
        G.nodes[sn]["stats"] = {
            "flows": agg_flows,
            "occupation": occupation,
            "member_count": len(mems),
        }


def _supernode_tooltip_text(n: Any, d: Dict[str, Any]) -> str:
    name = d.get("name") or str(n)
    stats = d.get("stats") or {}
    occ = stats.get("occupation")
    occ_str = "N/A" if occ is None else str(int(occ))
    flows = stats.get("flows", {})
    def fmt(bin_name: str) -> str:
        v = flows.get(bin_name)
        return "N/A" if v is None else str(int(round(float(v))))
    pop = d.get("source_population")
    dens = d.get("source_density")
    sink_m = d.get("sink_attraction_morning")
    sink_d = d.get("sink_attraction_day")
    sink_e = d.get("sink_attraction_evening")
    sink_n = d.get("sink_attraction_night")
    pop_str = "N/A" if pop is None else str(int(round(float(pop))))
    dens_str = "N/A" if dens is None else f"{float(dens):.1f}/km²"
    sink_str = (
        f"AM {('N/A' if sink_m is None else int(round(float(sink_m))))}, "
        f"Day {('N/A' if sink_d is None else int(round(float(sink_d))))}, "
        f"PM {('N/A' if sink_e is None else int(round(float(sink_e))))}, "
        f"Night {('N/A' if sink_n is None else int(round(float(sink_n))))}"
    )
    return (
        f"{name} — Occ: {occ_str} | Flow/hr: "
        f"AM {fmt('Morning rush')}, Day {fmt('Day')}, "
        f"PM {fmt('Evening rush')}, Night {fmt('Night')} | "
        f"Pop: {pop_str}, Dens: {dens_str}, Sink: {sink_str}"
    )


def _supernode_popup_html(n: Any, d: Dict[str, Any]) -> str:
    name = d.get("name") or str(n)
    stats = d.get("stats") or {}
    member_count = stats.get("member_count", 0)
    occ = stats.get("occupation")
    occ_str = "N/A" if occ is None else f"{int(occ)} (approx.)"
    flows = stats.get("flows", {})
    def fmt(bin_name: str) -> str:
        v = flows.get(bin_name)
        return "N/A" if v is None else str(int(round(float(v))))
    pop = d.get("source_population")
    dens = d.get("source_density")
    sink_m = d.get("sink_attraction_morning")
    sink_d = d.get("sink_attraction_day")
    sink_e = d.get("sink_attraction_evening")
    sink_n = d.get("sink_attraction_night")
    pop_str = "N/A" if pop is None else str(int(round(float(pop))))
    dens_str = "N/A" if dens is None else f"{float(dens):.1f} / km²"
    # Expected flows (if present)
    exp_out_m = d.get("expected_outflow_Morning") or d.get("expected_outflow_morning")
    exp_in_m = d.get("expected_inflow_Morning") or d.get("expected_inflow_morning")
    exp_out_d = d.get("expected_outflow_Day") or d.get("expected_outflow_day")
    exp_in_d = d.get("expected_inflow_Day") or d.get("expected_inflow_day")
    exp_out_e = d.get("expected_outflow_Evening") or d.get("expected_outflow_evening")
    exp_in_e = d.get("expected_inflow_Evening") or d.get("expected_inflow_evening")
    exp_out_n = d.get("expected_outflow_Night") or d.get("expected_outflow_night")
    exp_in_n = d.get("expected_inflow_Night") or d.get("expected_inflow_night")
    def fmt_flow(v: Any) -> str:
        return "N/A" if v is None else str(int(round(float(v))))
    rows = [
        f"<tr><th align='left'>Name</th><td>{name}</td></tr>",
        f"<tr><th align='left'>Member count</th><td>{member_count}</td></tr>",
        f"<tr><th align='left'>Occupation</th><td>{occ_str}</td></tr>",
        f"<tr><th align='left'>Population</th><td>{pop_str}</td></tr>",
        f"<tr><th align='left'>Density</th><td>{dens_str}</td></tr>",
        f"<tr><th align='left'>Flow/hr (AM)</th><td>{fmt('Morning rush')}</td></tr>",
        f"<tr><th align='left'>Flow/hr (Day)</th><td>{fmt('Day')}</td></tr>",
        f"<tr><th align='left'>Flow/hr (PM)</th><td>{fmt('Evening rush')}</td></tr>",
        f"<tr><th align='left'>Flow/hr (Night)</th><td>{fmt('Night')}</td></tr>",
        f"<tr><th align='left'>Sink (AM/Day/PM/Night)</th><td>{'N/A' if sink_m is None else int(round(float(sink_m)))}/"
        f"{'N/A' if sink_d is None else int(round(float(sink_d)))}/"
        f"{'N/A' if sink_e is None else int(round(float(sink_e)))}/"
        f"{'N/A' if sink_n is None else int(round(float(sink_n)))}</td></tr>",
        f"<tr><th align='left'>Expected outflow (AM/Day/PM/Night)</th><td>{fmt_flow(exp_out_m)}/{fmt_flow(exp_out_d)}/{fmt_flow(exp_out_e)}/{fmt_flow(exp_out_n)}</td></tr>",
        f"<tr><th align='left'>Expected inflow (AM/Day/PM/Night)</th><td>{fmt_flow(exp_in_m)}/{fmt_flow(exp_in_d)}/{fmt_flow(exp_in_e)}/{fmt_flow(exp_in_n)}</td></tr>",
    ]
    return "<table>" + "".join(rows) + "</table>"


def save_folium_flow_map(
    G: nx.MultiDiGraph,
    html_path: Path | str,
    scats_df: "pd.DataFrame | None" = None,
    time_bins: Dict[str, Dict[str, str]] | None = None,
    show_all_nodes: bool = True,
    width: int = 2,
) -> None:
    """Plot graph on a Folium map with flows and two node layers.

    - Edges: colored by mean of 'flow_series' (or a fallback using capacity).
    - Supernodes: larger markers with tooltip and popup. If scats_df provided,
      supernodes annotated with occupation and bin flows; else show N/A.
    - Junction nodes: all nodes plotted as a separate layer with small markers.
    - Saves to HTML at html_path.
    """
    html_path = Path(html_path)
    html_path.parent.mkdir(parents=True, exist_ok=True)

    cx, cy = _graph_center(G)
    fmap = folium.Map(location=(cy, cx), zoom_start=12, control_scale=True)

    # Precompute intensities for scaling
    intensities = []
    for u, v, k, d in G.edges(keys=True, data=True):
        intensities.append(_edge_intensity(d))
    if intensities:
        vmax = float(np.percentile(intensities, 95))
        vmin = float(np.percentile(intensities, 5))
    else:
        vmin, vmax = 0.0, 1.0

    # Draw edges as straight lines between node coords
    node_xy: Dict[Any, Tuple[float, float]] = {
        n: (d.get("x"), d.get("y")) for n, d in G.nodes(data=True)
        if d.get("x") is not None and d.get("y") is not None
    }
    for u, v, k, d in G.edges(keys=True, data=True):
        ux, uy = node_xy.get(u, (None, None))
        vx, vy = node_xy.get(v, (None, None))
        if ux is None or uy is None or vx is None or vy is None:
            continue
        val = _edge_intensity(d)
        color = _color_from_value(val, vmin, vmax)
        folium.PolyLine([(uy, ux), (vy, vx)], color=color, weight=width, opacity=0.9).add_to(fmap)

    # Optionally annotate graph with SCATS-derived stats
    if scats_df is not None:
        try:
            annotate_graph_with_scats(G, scats_df, time_bins)
        except Exception:
            # Graceful fallback: leave stats absent
            pass

    # Layers
    fg_super = folium.FeatureGroup(name="Supernodes", show=True)
    fg_junc = folium.FeatureGroup(name="Junction nodes", show=bool(show_all_nodes))

    # Mark supernodes with enhanced tooltips/popups
    for n, d in G.nodes(data=True):
        if d.get("is_supernode"):
            x, y = d.get("x"), d.get("y")
            if x is None or y is None:
                continue
            tip = _supernode_tooltip_text(n, d)
            pop = _supernode_popup_html(n, d)
            folium.CircleMarker(
                location=(y, x),
                radius=9,
                color="red",
                fill=True,
                fill_color="red",
                fill_opacity=0.9,
                tooltip=folium.Tooltip(tip, sticky=True),
                popup=folium.Popup(pop, max_width=350),
            ).add_to(fg_super)

    # Plot all junction nodes
    if show_all_nodes:
        for n, d in G.nodes(data=True):
            x, y = d.get("x"), d.get("y")
            if x is None or y is None:
                continue
            name = d.get("name") or str(n)
            folium.CircleMarker(
                location=(y, x),
                radius=3,
                color="blue",
                fill=True,
                fill_color="blue",
                fill_opacity=0.6,
                tooltip=folium.Tooltip(name, sticky=False),
            ).add_to(fg_junc)

    fg_super.add_to(fmap)
    fg_junc.add_to(fmap)
    folium.LayerControl(collapsed=False).add_to(fmap)

    fmap.save(str(html_path))


__all__ = [
    "save_folium_flow_map",
    "compute_node_stats",
    "annotate_graph_with_scats",
    "DEFAULT_TIME_BINS",
]

"""Visualisation helpers using Folium and OSMnx (placeholder)."""

from pathlib import Path
import folium
import osmnx as ox
import networkx as nx


def to_folium_map(G: nx.MultiDiGraph) -> folium.Map:
    """Return a simple Folium map with nodes plotted."""
    # Center map using graph's mean coordinates
    xs = [d["x"] for _, d in G.nodes(data=True)]
    ys = [d["y"] for _, d in G.nodes(data=True)]
    center = (sum(ys) / len(ys), sum(xs) / len(xs)) if xs and ys else (0.0, 0.0)
    m = folium.Map(location=center, zoom_start=12, control_scale=True)
    for n, d in G.nodes(data=True):
        folium.CircleMarker(location=(d["y"], d["x"]), radius=2, color="blue", fill=True, fill_opacity=0.6).add_to(m)
    return m


def save_folium_map(m: folium.Map, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(path))


def save_osmnx_plot(G: nx.MultiDiGraph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ox.plot_graph(G, show=False, save=True, filepath=str(path))


