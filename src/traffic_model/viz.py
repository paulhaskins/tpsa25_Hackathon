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
import math


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


# Unified color mapping for all object types
COLORS = {
    'supernode': '#3B82F6',    # blue
    'junction': '#F59E0B',     # amber
    'source': '#10B981',       # emerald/green
    'sink': '#EF4444',         # red
    # Legacy category colors for backward compatibility
    'Residential': '#10B981',  # emerald/green (sources)
    'Business': '#EF4444',     # red (sinks)
    'School': '#9370DB',       # Medium purple (education)
    'Hospital': '#DC143C',     # Crimson (healthcare)
    'Transport': '#F59E0B',    # amber (junctions)
    'Other': '#808080'         # Gray (other)
}

def _get_category_color(category: str) -> str:
    """Get color for node category using unified color mapping."""
    return COLORS.get(category, COLORS['Other'])


def _scale_marker_radius(capacity: float, time_of_day: str = "day", category: str = "Other") -> float:
    """Scale marker radius based on population capacity and time-of-day demand."""
    # Base radius from log(capacity)
    base_radius = max(5, min(30, math.log1p(capacity)))
    
    # Apply time-of-day demand factor
    from .population import TIME_PROFILE
    demand_factor = TIME_PROFILE.get(category, TIME_PROFILE["Other"]).get(time_of_day, 1.0)
    
    # Scale radius by demand factor
    scaled_radius = base_radius * (0.5 + 0.5 * demand_factor)
    return max(3, min(35, scaled_radius))


def _add_legend_to_map(fmap: folium.Map) -> None:
    """Add a legend to the map showing object type colors (bottom-right positioned)."""
    legend_html = '''
    <div style="position: fixed; 
                bottom: 50px; right: 50px; width: 180px; height: 120px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:12px; padding: 10px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.2)">
    <p style="margin: 0 0 8px 0; font-weight: bold; text-align: center;">Object Types</p>
    <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#3B82F6"></i> Supernode</p>
    <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#F59E0B"></i> Junction</p>
    <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#10B981"></i> Source</p>
    <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#EF4444"></i> Sink</p>
    </div>
    '''
    fmap.get_root().html.add_child(folium.Element(legend_html))


def _add_choropleth_layer(fmap: folium.Map, census_data_path: Path) -> bool:
    """Add a choropleth layer for population density if census data exists."""
    try:
        import geopandas as gpd
        
        # Check if file exists
        if not census_data_path.exists():
            print(f"Census data file not found: {census_data_path}")
            return False
        
        # Try to load census data with geometries
        if census_data_path.suffix.lower() == '.csv':
            # Try to load as CSV with geometry column
            df = pd.read_csv(census_data_path)
            if 'geometry' in df.columns:
                # Convert geometry strings to actual geometries
                from shapely import wkt
                df['geometry'] = df['geometry'].apply(wkt.loads)
                gdf = gpd.GeoDataFrame(df, geometry='geometry')
            else:
                return False
        elif census_data_path.suffix.lower() in ['.geojson', '.json']:
            # Check if it's a JSON-stat file by looking for the "class" field
            try:
                import json
                with open(census_data_path, 'r') as f:
                    first_chars = f.read(100)
                    if '"class":"dataset"' in first_chars:
                        # This is a JSON-stat file, use the population loading function
                        from .population import load_census_data
                        boundaries_path = census_data_path.parent / "small_area_boundaries_2022.geojson"
                        if boundaries_path.exists():
                            gdf = load_census_data(census_data_path, boundaries_path)
                            if gdf is None:
                                return False
                        else:
                            print(f"Info: Boundaries file not found: {boundaries_path}")
                            return False
                    else:
                        # This is a regular GeoJSON file
                        gdf = gpd.read_file(census_data_path)
            except Exception as e:
                print(f"Info: Could not read census data file: {e}")
                return False
        elif census_data_path.suffix.lower() == '.px':
            # For .px files, use the population loading function
            try:
                from .population import load_census_data
                boundaries_path = census_data_path.parent / "small_area_boundaries_2022.geojson"
                if boundaries_path.exists():
                    gdf = load_census_data(census_data_path, boundaries_path)
                    if gdf is None:
                        return False
                else:
                    print(f"Info: Boundaries file not found: {boundaries_path}")
                    return False
            except Exception as e:
                print(f"Info: Could not load .px census data: {e}")
                return False
        else:
            print(f"Unsupported file format for census data: {census_data_path.suffix}")
            return False
        
        # Check if we have population data
        pop_columns = [col for col in gdf.columns if 'population' in col.lower() or 'density' in col.lower()]
        if not pop_columns:
            return False
        
        pop_col = pop_columns[0]  # Use first population column found
        
        # Create choropleth layer
        # Use the first available identifier column or create one
        id_col = None
        for col in ['SA_PUB2022', 'SA_PUB2016', 'OBJECTID', 'id']:
            if col in gdf.columns:
                id_col = col
                break
        
        if id_col is None:
            # Create a simple ID column
            gdf['id'] = range(len(gdf))
            id_col = 'id'
        
        # Add choropleth directly to the map (not to a FeatureGroup)
        # Make it non-interactive to avoid blocking clicks on other layers
        choropleth = folium.Choropleth(
            geo_data=gdf.to_json(),
            data=gdf,
            columns=[id_col, pop_col],
            key_on=f'feature.properties.{id_col}',
            fill_color='YlOrRd',
            fill_opacity=0.7,
            line_opacity=0.2,
            legend_name=f'Population {pop_col}',
            name='Population Density'
        )
        
        # Add custom CSS to make choropleth non-interactive
        choropleth_html = """
        <style>
        .leaflet-interactive {
            pointer-events: none !important;
        }
        </style>
        """
        fmap.get_root().html.add_child(folium.Element(choropleth_html))
        
        choropleth.add_to(fmap)
        
        return True
    except ImportError:
        print("geopandas not available, skipping choropleth layer")
        return False
    except Exception as e:
        print(f"Error adding choropleth layer: {e}")
        return False


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
    """Create clean popup for supernode objects."""
    import html
    
    name = d.get("name") or str(n)
    stats = d.get("stats") or {}
    member_count = stats.get("member_count", 0)
    
    # Get exits count (1 or 2)
    exits_count = d.get("exits_count", 1)
    
    # Population capacity and demand profile
    pop_capacity = d.get("population_capacity")
    pop_capacity_str = "N/A" if pop_capacity is None else str(int(round(float(pop_capacity))))
    
    demand_profile = d.get("demand_profile", {})
    demand_str = "N/A"
    if demand_profile:
        demand_parts = []
        for time_period, factor in demand_profile.items():
            if isinstance(factor, (int, float)):
                demand_parts.append(f"{time_period}: {factor:.1f}")
        if demand_parts:
            demand_str = ", ".join(demand_parts)
    
    # Category
    category = d.get("category", "Unknown")
    
    # Tags summary
    tags_summary = []
    for key, value in d.items():
        if key not in ['x', 'y', 'lat', 'lon', 'is_supernode', 'members', 'population_capacity', 'demand_profile', 'category', 'stats']:
            if isinstance(value, (str, int, float)) and len(str(value)) < 50:
                tags_summary.append(f"{key}: {value}")
    
    tags_str = ", ".join(tags_summary[:3]) if tags_summary else "None"
    if len(tags_summary) > 3:
        tags_str += "..."
    
    # Create clean, formatted popup content
    popup_content = f"""<div style="font-family: Arial, sans-serif; font-size: 12px; line-height: 1.4; max-width: 280px;">
<h3 style="margin: 0 0 8px 0; color: #2c3e50; font-size: 14px;">{html.escape(str(name))}</h3>
<div style="background-color: #f8f9fa; padding: 8px; border-radius: 4px; margin-bottom: 8px;">
<p style="margin: 2px 0;"><strong>Type:</strong> Supernode</p>
<p style="margin: 2px 0;"><strong>Exits:</strong> {exits_count}</p>
<p style="margin: 2px 0;"><strong>Members:</strong> {member_count}</p>
</div>
<p style="margin: 4px 0;"><strong>Category:</strong> {category}</p>
<p style="margin: 4px 0;"><strong>Population Capacity:</strong> {pop_capacity_str}</p>
<p style="margin: 4px 0;"><strong>Demand Profile:</strong> {demand_str}</p>
<p style="margin: 4px 0;"><strong>Tags:</strong> {html.escape(tags_str)}</p>
</div>"""
    
    return popup_content


def _create_supernode_popup(n: Any, d: Dict[str, Any]) -> folium.Popup:
    """Create a folium popup for supernode objects."""
    html_content = _supernode_popup_html(n, d)
    return folium.Popup(folium.Html(html_content, script=True), max_width=350)


def _junction_popup_html(node_id: Any, node_data: Dict[str, Any]) -> str:
    """Create clean popup for junction objects."""
    import html
    
    degree = node_data.get('degree', 0)
    has_traffic_light = node_data.get('has_traffic_light', False)
    efficiency = node_data.get('efficiency', 1.0)
    
    traffic_light_text = "Yes" if has_traffic_light else "No"
    efficiency_text = f"{efficiency:.2f}" if efficiency is not None else "N/A"
    
    popup_content = f"""<div style="font-family: Arial, sans-serif; font-size: 12px; line-height: 1.4; max-width: 280px;">
<h3 style="margin: 0 0 8px 0; color: #2c3e50; font-size: 14px;">Junction {html.escape(str(node_id))}</h3>
<div style="background-color: #f8f9fa; padding: 8px; border-radius: 4px; margin-bottom: 8px;">
<p style="margin: 2px 0;"><strong>Type:</strong> Junction</p>
<p style="margin: 2px 0;"><strong>Degree:</strong> {degree}</p>
<p style="margin: 2px 0;"><strong>Traffic Light:</strong> {traffic_light_text}</p>
<p style="margin: 2px 0;"><strong>Efficiency:</strong> {efficiency_text}</p>
</div>
</div>"""
    
    return popup_content


def _create_junction_popup(node_id: Any, node_data: Dict[str, Any]) -> folium.Popup:
    """Create a folium popup for junction objects."""
    html_content = _junction_popup_html(node_id, node_data)
    return folium.Popup(folium.Html(html_content, script=True), max_width=300)


def _source_popup_html(node_id: Any, node_data: Dict[str, Any]) -> str:
    """Create clean popup for source objects."""
    import html
    
    pop_capacity = node_data.get('population_capacity', 0)
    demand_profile = node_data.get('demand_profile', {})
    
    demand_str = "N/A"
    if demand_profile:
        demand_parts = []
        for time_period, factor in demand_profile.items():
            if isinstance(factor, (int, float)):
                demand_parts.append(f"{time_period}: {factor:.1f}")
        if demand_parts:
            demand_str = ", ".join(demand_parts)
    
    popup_content = f"""<div style="font-family: Arial, sans-serif; font-size: 12px; line-height: 1.4; max-width: 280px;">
<h3 style="margin: 0 0 8px 0; color: #2c3e50; font-size: 14px;">Source {html.escape(str(node_id))}</h3>
<div style="background-color: #f8f9fa; padding: 8px; border-radius: 4px; margin-bottom: 8px;">
<p style="margin: 2px 0;"><strong>Type:</strong> Source (Residential)</p>
<p style="margin: 2px 0;"><strong>Population Capacity:</strong> {pop_capacity}</p>
<p style="margin: 2px 0;"><strong>Demand Profile:</strong> {demand_str}</p>
</div>
</div>"""
    
    return popup_content


def _create_source_popup(node_id: Any, node_data: Dict[str, Any]) -> folium.Popup:
    """Create a folium popup for source objects."""
    html_content = _source_popup_html(node_id, node_data)
    return folium.Popup(folium.Html(html_content, script=True), max_width=300)


def _sink_popup_html(node_id: Any, node_data: Dict[str, Any]) -> str:
    """Create clean popup for sink objects."""
    import html
    
    office_name = node_data.get('name') or node_data.get('business_name', 'Unknown Office')
    office_type = node_data.get('place_type') or node_data.get('google_place_type') or node_data.get('business_type', 'Office')
    person_capacity = node_data.get('population_capacity', 0)
    
    # Demand weights for sink attraction
    demand_weights = {}
    for key, value in node_data.items():
        if 'sink_attraction' in key.lower():
            time_period = key.replace('sink_attraction_', '').replace('_', ' ').title()
            demand_weights[time_period] = value
    
    demand_str = "N/A"
    if demand_weights:
        demand_parts = []
        for time_period, weight in demand_weights.items():
            if isinstance(weight, (int, float)):
                demand_parts.append(f"{time_period}: {weight:.1f}")
        if demand_parts:
            demand_str = ", ".join(demand_parts)
    
    popup_content = f"""<div style="font-family: Arial, sans-serif; font-size: 12px; line-height: 1.4; max-width: 280px;">
<h3 style="margin: 0 0 8px 0; color: #2c3e50; font-size: 14px;">{html.escape(str(office_name))}</h3>
<div style="background-color: #f8f9fa; padding: 8px; border-radius: 4px; margin-bottom: 8px;">
<p style="margin: 2px 0;"><strong>Type:</strong> Sink (Office)</p>
<p style="margin: 2px 0;"><strong>Office Type:</strong> {html.escape(str(office_type))}</p>
<p style="margin: 2px 0;"><strong>Person Capacity:</strong> {person_capacity}</p>
<p style="margin: 2px 0;"><strong>Demand Weights:</strong> {demand_str}</p>
</div>
</div>"""
    
    return popup_content


def _create_sink_popup(node_id: Any, node_data: Dict[str, Any]) -> folium.Popup:
    """Create a folium popup for sink objects."""
    html_content = _sink_popup_html(node_id, node_data)
    return folium.Popup(folium.Html(html_content, script=True), max_width=300)


def _create_poi_popup(node_id: Any, node_data: Dict[str, Any], category: str) -> str:
    """Create a clean popup for POI nodes (legacy function)."""
    import html
    
    # Get basic information
    name = node_data.get('name', f'POI {node_id}')
    population_capacity = node_data.get('population_capacity', 0)
    business_name = node_data.get('business_name', '')
    business_type = node_data.get('business_type', '')
    
    # Create popup content
    popup_content = f"""<div style="font-family: Arial, sans-serif; font-size: 12px; line-height: 1.4; max-width: 280px;">
<h3 style="margin: 0 0 8px 0; color: #2c3e50; font-size: 14px;">{html.escape(str(name))}</h3>
<div style="background-color: #f8f9fa; padding: 8px; border-radius: 4px; margin-bottom: 8px;">
<p style="margin: 2px 0;"><strong>Category:</strong> {category}</p>
<p style="margin: 2px 0;"><strong>Population Capacity:</strong> {population_capacity}</p>"""
    
    # Add business-specific information if available
    if business_name:
        popup_content += f"""<p style="margin: 2px 0;"><strong>Business Name:</strong> {html.escape(str(business_name))}</p>"""
    
    if business_type:
        popup_content += f"""<p style="margin: 2px 0;"><strong>Business Type:</strong> {html.escape(str(business_type))}</p>"""
    
    popup_content += """</div>
</div>"""
    
    return popup_content


def _create_poi_popup_iframe(node_id: Any, node_data: Dict[str, Any], category: str) -> folium.Popup:
    """Create a folium popup for POI nodes."""
    html_content = _create_poi_popup(node_id, node_data, category)
    return folium.Popup(folium.Html(html_content, script=True), max_width=300)


def save_folium_flow_map(
    G: nx.MultiDiGraph,
    html_path: Path | str,
    scats_df: "pd.DataFrame | None" = None,
    time_bins: Dict[str, Dict[str, str]] | None = None,
    show_all_nodes: bool = True,
    width: int = 2,
    time_of_day: str = "day",
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
            
            # Get category and population capacity
            category = d.get("category", "Other")
            pop_capacity = d.get("population_capacity", 100)
            
            # Scale radius based on capacity and time-of-day
            radius = _scale_marker_radius(pop_capacity, time_of_day, category)
            
            # Color by category
            color = _get_category_color(category)
            
            tip = _supernode_tooltip_text(n, d)
            pop = _supernode_popup_html(n, d)
            
            # Create popup with error handling
            import html
            try:
                popup = folium.Popup(folium.Html(pop, script=True), max_width=350)
            except Exception as e:
                print(f"Error creating popup for node {n}: {e}")
                # Fallback to simple popup
                name = d.get("name") or str(n)
                category = d.get("category", "Unknown")
                popup = folium.Popup(folium.Html(f"<b>{html.escape(str(name))}</b><br>Category: {category}", script=True), max_width=200)
            
            folium.CircleMarker(
                location=(y, x),
                radius=radius,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.9,
                tooltip=folium.Tooltip(tip, sticky=True),
                popup=popup,
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
    "save_enhanced_folium_map",
    "compute_node_stats",
    "annotate_graph_with_scats",
    "DEFAULT_TIME_BINS",
    "COLORS",
    "_get_category_color",
    "_scale_marker_radius",
    "_add_legend_to_map",
    "_add_choropleth_layer",
    "_supernode_popup_html",
    "_junction_popup_html",
    "_source_popup_html",
    "_sink_popup_html",
    "_create_supernode_popup",
    "_create_junction_popup",
    "_create_source_popup",
    "_create_sink_popup",
    "_create_poi_popup_iframe",
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


def save_enhanced_folium_map(
    G: nx.MultiDiGraph,
    html_path: Path | str,
    layers: str = "all",
    scats_df: "pd.DataFrame | None" = None,
    time_bins: Dict[str, Dict[str, str]] | None = None,
    width: int = 2,
    time_of_day: str = "day",
    census_data_path: Optional[Path] = None,
) -> None:
    """
    Create an enhanced Folium map with multiple layers and controls.

    Args:
        G: NetworkX graph with capacity, category, and efficiency annotations
        html_path: Output HTML file path
        layers: Which layers to include ("roads", "supernodes", "junctions", "categories", "all")
        scats_df: Optional SCATS data for flow visualization
        time_bins: Time bins for flow analysis
        width: Edge width for roads layer
    """
    html_path = Path(html_path)
    html_path.parent.mkdir(parents=True, exist_ok=True)

    # Get map center
    cx, cy = _graph_center(G)
    fmap = folium.Map(location=(cy, cx), zoom_start=12, control_scale=True)

    # Parse layers
    show_roads = layers in ["roads", "all"]
    show_supernodes = layers in ["supernodes", "all"]
    show_junctions = layers in ["junctions", "all"]
    show_categories = layers in ["categories", "all"]

    # Roads layer - colored by saturation (load/capacity)
    if show_roads:
        fg_roads = folium.FeatureGroup(name="Roads", show=True)
        
        # Precompute intensities for scaling
        intensities = []
        for u, v, k, d in G.edges(keys=True, data=True):
            # Calculate saturation as load/capacity
            capacity = d.get('capacity', 1)
            load = _edge_intensity(d)
            saturation = load / capacity if capacity > 0 else 0
            intensities.append(saturation)
        
        if intensities:
            vmax = float(np.percentile(intensities, 95))
            vmin = float(np.percentile(intensities, 5))
        else:
            vmin, vmax = 0.0, 1.0

        # Draw edges
        node_xy: Dict[Any, Tuple[float, float]] = {
            n: (d.get("x"), d.get("y")) for n, d in G.nodes(data=True)
            if d.get("x") is not None and d.get("y") is not None
        }
        
        for u, v, k, d in G.edges(keys=True, data=True):
            ux, uy = node_xy.get(u, (None, None))
            vx, vy = node_xy.get(v, (None, None))
            if ux is None or uy is None or vx is None or vy is None:
                continue
            
            # Calculate saturation
            capacity = d.get('capacity', 1)
            load = _edge_intensity(d)
            saturation = load / capacity if capacity > 0 else 0
            color = _color_from_value(saturation, vmin, vmax)
            
            # Create popup with edge information
            name = d.get('name', 'Unnamed Road')
            lanes = d.get('lanes', 1)
            length = d.get('length', 0)
            popup_text = f"""
            <b>{name}</b><br>
            Lanes: {lanes}<br>
            Length: {length:.1f}m<br>
            Capacity: {capacity}<br>
            Current Load: {load:.1f}<br>
            Saturation: {saturation:.2f}
            """
            
            folium.PolyLine(
                [(uy, ux), (vy, vx)], 
                color=color, 
                weight=width, 
                opacity=0.9,
                popup=folium.Popup(popup_text, max_width=200)
            ).add_to(fg_roads)
        
        fg_roads.add_to(fmap)

    # Supernodes layer
    if show_supernodes:
        fg_super = folium.FeatureGroup(name="Supernodes", show=True)
        
        for n, d in G.nodes(data=True):
            if d.get("is_supernode"):
                x, y = d.get("x"), d.get("y")
                if x is None or y is None:
                    continue
                
                # Get category and population capacity
                category = d.get("category", "Other")
                pop_capacity = d.get('population_capacity', 100)
                
                # Scale radius based on capacity and time-of-day
                radius = _scale_marker_radius(pop_capacity, time_of_day, category)
                
                # Use supernode color from unified color scheme
                color = COLORS['supernode']
                
                # Create enhanced popup with IFrame
                try:
                    popup = _create_supernode_popup(n, d)
                except Exception as e:
                    print(f"Error creating popup for node {n}: {e}")
                    # Fallback to simple popup
                    import html
                    popup = folium.Popup(folium.Html(f"<b>{html.escape(str(n))}</b><br>Type: Supernode", script=True), max_width=200)
                
                folium.CircleMarker(
                    location=(y, x),
                    radius=radius,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.7,
                    popup=popup
                ).add_to(fg_super)
        
        fg_super.add_to(fmap)

    # Junctions layer
    if show_junctions:
        fg_junc = folium.FeatureGroup(name="Junctions", show=True)
        
        for n, d in G.nodes(data=True):
            if G.degree(n) >= 3:  # Junction nodes
                x, y = d.get("x"), d.get("y")
                if x is None or y is None:
                    continue
                
                # Add degree to node data for popup
                d['degree'] = G.degree(n)
                
                # Use junction color from unified color scheme
                color = COLORS['junction']
                
                # Create clean popup with IFrame
                try:
                    popup = _create_junction_popup(n, d)
                except Exception as e:
                    print(f"Error creating popup for node {n}: {e}")
                    # Fallback to simple popup
                    import html
                    popup = folium.Popup(folium.Html(f"<b>Junction {html.escape(str(n))}</b><br>Degree: {d['degree']}", script=True), max_width=200)
                
                folium.CircleMarker(
                    location=(y, x),
                    radius=6,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.8,
                    popup=popup
                ).add_to(fg_junc)
        
        fg_junc.add_to(fmap)

    # Sources and Sinks layers
    if show_categories:
        # Sources layer (Residential)
        fg_sources = folium.FeatureGroup(name="Sources", show=False)
        for n, d in G.nodes(data=True):
            if d.get('category') == 'Residential' and not d.get('is_supernode'):
                x, y = d.get("x"), d.get("y")
                if x is None or y is None:
                    continue
                
                # Use source color
                color = COLORS['source']
                
                # Create source popup with IFrame
                try:
                    popup = _create_source_popup(n, d)
                except Exception as e:
                    print(f"Error creating popup for node {n}: {e}")
                    # Fallback to simple popup
                    import html
                    popup = folium.Popup(folium.Html(f"<b>Source {html.escape(str(n))}</b><br>Capacity: {d.get('population_capacity', 0)}", script=True), max_width=200)
                
                folium.CircleMarker(
                    location=(y, x),
                    radius=5,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.8,
                    popup=popup
                ).add_to(fg_sources)
        
        fg_sources.add_to(fmap)
        
        # Sinks layer (Business/Office)
        fg_sinks = folium.FeatureGroup(name="Sinks", show=False)
        for n, d in G.nodes(data=True):
            if d.get('category') == 'Business' and not d.get('is_supernode'):
                x, y = d.get("x"), d.get("y")
                if x is None or y is None:
                    continue
                
                # Use sink color
                color = COLORS['sink']
                
                # Create sink popup with IFrame
                try:
                    popup = _create_sink_popup(n, d)
                except Exception as e:
                    print(f"Error creating popup for node {n}: {e}")
                    # Fallback to simple popup
                    import html
                    office_name = d.get('name', 'Unknown Office')
                    popup = folium.Popup(folium.Html(f"<b>{html.escape(str(office_name))}</b><br>Type: Sink", script=True), max_width=200)
                
                folium.CircleMarker(
                    location=(y, x),
                    radius=5,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.8,
                    popup=popup
                ).add_to(fg_sinks)
        
        fg_sinks.add_to(fmap)
        
        # Other categories (School, Hospital, Transport, Other)
        other_categories = ['School', 'Hospital', 'Transport', 'Other']
        for category in other_categories:
            fg_cat = folium.FeatureGroup(name=f"{category}", show=False)
            
            for n, d in G.nodes(data=True):
                if d.get('category') == category and not d.get('is_supernode'):
                    x, y = d.get("x"), d.get("y")
                    if x is None or y is None:
                        continue
                    
                    # Use legacy category colors for other types
                    color = _get_category_color(category)
                    
                    # Create POI popup with IFrame
                    try:
                        popup = _create_poi_popup_iframe(n, d, category)
                    except Exception as e:
                        print(f"Error creating popup for node {n}: {e}")
                        # Fallback to simple popup
                        import html
                        name = d.get('name', f'POI {n}')
                        popup = folium.Popup(folium.Html(f"<b>{html.escape(str(name))}</b><br>Category: {category}", script=True), max_width=200)
                    
                    folium.CircleMarker(
                        location=(y, x),
                        radius=4,
                        color=color,
                        fill=True,
                        fill_color=color,
                        fill_opacity=0.7,
                        popup=popup
                    ).add_to(fg_cat)
            
            fg_cat.add_to(fmap)

    # Add choropleth layer if census data is available
    if census_data_path and census_data_path.exists():
        _add_choropleth_layer(fmap, census_data_path)
    
    # Add layer control with proper positioning (top-right)
    layer_control = folium.LayerControl(collapsed=False, position='topright')
    layer_control.add_to(fmap)
    
    # Add custom CSS to ensure layer control fits on screen
    layer_control_html = """
    <style>
    .leaflet-control-layers {
        max-height: 80vh !important;
        overflow-y: auto !important;
        font-size: 12px !important;
    }
    .leaflet-control-layers-list {
        max-height: 70vh !important;
        overflow-y: auto !important;
    }
    </style>
    """
    fmap.get_root().html.add_child(folium.Element(layer_control_html))
    
    # Add legend
    _add_legend_to_map(fmap)
    
    # Save map
    fmap.save(str(html_path))


