"""Population, attraction, and expected-flow estimation utilities.

Implements a robust pipeline to estimate residential sources, sink attractions,
and expected flows between supernodes using a gravity-style model, with graceful
fallbacks when some datasets are missing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any

import pandas as pd
import geopandas as gpd
import numpy as np
import networkx as nx

from shapely.geometry import Point, Polygon, MultiPolygon
from shapely.ops import unary_union


# -----------------------------
# Config and constants
# -----------------------------

DEFAULT_TIME_BINS: Dict[str, Dict[str, str]] = {
    "Morning rush": {"start": "06:30", "end": "09:30"},
    "Day": {"start": "09:30", "end": "16:30"},
    "Evening rush": {"start": "16:30", "end": "19:30"},
    "Night": {"start": "19:30", "end": "06:30"},
}

POI_WEIGHTS: Dict[str, int] = {
    "office": 3,
    "retail": 2,
    "school": 4,
    "university": 4,
    "hospital": 5,
    "government": 3,
    "industrial": 2,
    "leisure": 1,
    "airport": 5,
    "rail": 5,
    "transport": 5,
}

TIME_WEIGHTS: Dict[str, Dict[str, float]] = {
    # Per time bin multipliers by coarse category. Used when jobs are absent.
    "Morning rush": {"work": 1.2, "education": 1.2, "health": 1.2, "leisure": 0.5, "transport": 1.2},
    "Day": {"work": 1.0, "education": 1.0, "health": 1.0, "leisure": 1.0, "transport": 1.0},
    "Evening rush": {"work": 0.6, "education": 0.6, "health": 1.0, "leisure": 1.1, "transport": 1.0},
    "Night": {"work": 0.3, "education": 0.3, "health": 1.3, "leisure": 0.3, "transport": 1.3},
}


# -----------------------------
# 1) Loaders
# -----------------------------

def load_census_geometries(path: Path | str, pop_field: str = "population") -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path)
    if pop_field not in gdf.columns:
        raise ValueError(f"Population field '{pop_field}' not found in census geometries")
    gdf = gdf[~gdf.geometry.isna()].copy()
    return gdf


def load_landuse_mask(path: Path | str, residential_tags: Optional[List[str]] = None) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path)
    residential_tags = residential_tags or [
        "residential", "apartments", "terrace", "house", "detached", "semidetached",
    ]
    # Try to filter by plausible columns if present
    filters: List[pd.Series] = []
    for col in ["landuse", "building", "amenity", "type", "class", "category"]:
        if col in gdf.columns:
            filters.append(gdf[col].astype(str).str.lower().isin(residential_tags))
    if filters:
        mask = np.logical_or.reduce(filters)
        gdf = gdf[mask].copy()
    gdf = gdf[~gdf.geometry.isna()].copy()
    return gdf


def load_pois_or_jobs(path: Path | str, jobs_field: Optional[str] = "jobs") -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path)
    gdf = gdf[~gdf.geometry.isna()].copy()
    # If jobs_field not present, we will use POI weights later
    return gdf


# -----------------------------
# 2) Catchments for nodes
# -----------------------------

def _graph_nodes_gdf(G: nx.MultiDiGraph, crs_proj: str) -> gpd.GeoDataFrame:
    rows: List[Dict[str, Any]] = []
    for n, d in G.nodes(data=True):
        x = d.get("x")
        y = d.get("y")
        if x is None or y is None:
            continue
        rows.append({"node": n, "geometry": Point(float(x), float(y))})
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    return gdf.to_crs(crs_proj)


def build_node_catchments(G, method: str = "voronoi", buffer_m: int = 250, crs_projected: str = "EPSG:2157") -> gpd.GeoDataFrame:
    """
    Returns GeoDataFrame with one polygon per node id: fields ['node','geometry','area_km2'].
    method='voronoi' in projected CRS; if fallback, use buffered circles at given meters.
    """
    pts = _graph_nodes_gdf(G, crs_projected)
    if pts.empty:
        return gpd.GeoDataFrame(columns=["node", "geometry", "area_km2"], geometry="geometry", crs=crs_projected)

    if method == "voronoi":
        try:
            from shapely.ops import voronoi_diagram
            hull = unary_union(pts.geometry).convex_hull.buffer(1000)
            vd = voronoi_diagram(unary_union(pts.geometry), envelope=hull, edges=False)
            # Match polygons to nearest points
            # Build spatial index of polygons
            polys = list(vd.geoms) if hasattr(vd, "geoms") else [vd]
            poly_gdf = gpd.GeoDataFrame({"geometry": polys}, crs=crs_projected)
            # Assign each polygon to nearest point
            idxs = poly_gdf.sindex
            assignments: Dict[int, Polygon] = {}
            for _, row in pts.iterrows():
                point = row.geometry
                cand_idx = list(idxs.nearest(point.bounds, 1))
                if not cand_idx:
                    continue
                poly = poly_gdf.iloc[cand_idx[0]].geometry
                if isinstance(poly, (Polygon, MultiPolygon)):
                    assignments[row.node] = Polygon(poly) if isinstance(poly, Polygon) else unary_union(poly)
            rows: List[Dict[str, Any]] = []
            for node, geom in assignments.items():
                rows.append({"node": node, "geometry": geom})
            out = gpd.GeoDataFrame(rows, geometry="geometry", crs=crs_projected)
        except Exception:
            # Fallback to buffers
            out = pts.copy()
            out["geometry"] = out.buffer(buffer_m)
    else:
        out = pts.copy()
        out["geometry"] = out.buffer(buffer_m)

    out["area_km2"] = out.geometry.area / 1_000_000.0
    return out[["node", "geometry", "area_km2"]]


# -----------------------------
# 3) Dasymetric areal interpolation
# -----------------------------

def dasymetric_allocate_population(
    census_gdf: gpd.GeoDataFrame,
    res_mask_gdf: Optional[gpd.GeoDataFrame],
    catchments_gdf: gpd.GeoDataFrame,
    pop_field: str = "population",
) -> pd.DataFrame:
    """
    Returns DataFrame indexed by node id with ['source_population','source_density'].
    """
    if census_gdf is None or census_gdf.empty:
        # No census; return zeros to allow graceful flow of pipeline
        out = pd.DataFrame({
            "node": catchments_gdf["node"],
            "source_population": 0.0,
            "source_density": 0.0,
        }).set_index("node")
        return out

    crs = catchments_gdf.crs
    cns = census_gdf.to_crs(crs)
    if res_mask_gdf is not None and not res_mask_gdf.empty:
        res = res_mask_gdf.to_crs(crs)
        # Intersect census polygons with residential mask
        res_inter = gpd.overlay(cns, res, how="intersection")
        res_inter["res_area"] = res_inter.geometry.area
        # Total residential area per census unit
        res_tot = res_inter.groupby(cns.index.name or cns.reset_index().columns[0])["res_area"].sum()
        cns = cns.reset_index(drop=False)
        cid = cns.columns[0]
        res_inter = res_inter.merge(res_tot.rename("res_total"), left_on=cid, right_index=True, how="left")
        # If a polygon has zero residential area, fallback to full area
        cns["poly_area"] = cns.geometry.area
        res_inter["res_total"] = res_inter["res_total"].replace({0.0: np.nan})
        res_inter["res_total"].fillna(cns.set_index(cid)["poly_area"], inplace=True)
        # Compute residential density (pop per residential area)
        cns = cns.set_index(cid)
        res_inter["pop_density"] = (res_inter[cns.columns.tolist()].merge(
            cns[[pop_field]], left_on=cid, right_index=True, how="left")[pop_field]
        ) / res_inter["res_total"].replace({0: np.nan})
        # Clip to catchments and sum allocated population
        inter2 = gpd.overlay(res_inter[[cid, "pop_density", "geometry"]], catchments_gdf, how="intersection")
        inter2["allocated_pop"] = inter2["pop_density"] * inter2.geometry.area
        node_pop = inter2.groupby("node")["allocated_pop"].sum()
    else:
        # Simple areal weighting: intersect census with catchments and allocate by area share
        inter = gpd.overlay(cns[[pop_field, "geometry"]], catchments_gdf, how="intersection")
        inter["area"] = inter.geometry.area
        # total area per census polygon
        cns2 = cns.copy()
        cns2["poly_area"] = cns2.geometry.area
        inter = inter.join(cns2[["poly_area"]], how="left")
        inter["allocated_pop"] = inter[pop_field] * (inter["area"] / inter["poly_area"]).replace({0: np.nan})
        node_pop = inter.groupby("node")["allocated_pop"].sum()

    out = catchments_gdf[["node", "area_km2"]].copy()
    out = out.set_index("node")
    out["source_population"] = node_pop.reindex(out.index).fillna(0.0)
    # Density per km2; clamp to plausible bounds if needed
    area = out["area_km2"].replace({0.0: np.nan})
    out["source_density"] = (out["source_population"] / area).replace({np.inf: 0.0}).fillna(0.0)
    return out[["source_population", "source_density"]]


# -----------------------------
# 4) Sink attraction
# -----------------------------

def _poi_category(row: pd.Series) -> str:
    t = str(row.get("poi_type", row.get("type", row.get("amenity", "")))).lower()
    if any(k in t for k in ["school", "university", "college"]):
        return "education"
    if any(k in t for k in ["hospital", "clinic", "health"]):
        return "health"
    if any(k in t for k in ["office", "government", "industrial"]):
        return "work"
    if any(k in t for k in ["airport", "rail", "bus", "station", "transport"]):
        return "transport"
    if any(k in t for k in ["shop", "retail", "mall", "leisure", "restaurant", "bar", "cinema"]):
        return "leisure"
    return "work"


def compute_sink_attraction(
    pois_jobs_gdf: Optional[gpd.GeoDataFrame],
    catchments_gdf: gpd.GeoDataFrame,
    jobs_field: Optional[str] = "jobs",
) -> pd.DataFrame:
    """
    Returns DataFrame indexed by node with columns:
    ['sink_attraction_base', 'sink_attraction_morning', 'sink_attraction_day',
     'sink_attraction_evening', 'sink_attraction_night']
    """
    base = pd.DataFrame(index=catchments_gdf["node"])
    base.index.name = "node"
    if pois_jobs_gdf is None or pois_jobs_gdf.empty:
        # No POIs/jobs; set zeros
        base["sink_attraction_base"] = 0.0
    else:
        crs = catchments_gdf.crs
        pj = pois_jobs_gdf.to_crs(crs)
        # Spatial join: which catchment contains each POI/job
        pj_in = gpd.sjoin(pj, catchments_gdf[["node", "geometry"]], how="left", predicate="within")
        pj_in = pj_in.dropna(subset=["node"]) if "node" in pj_in.columns else pj_in
        if jobs_field and jobs_field in pj_in.columns:
            grouped = pj_in.groupby("node")[jobs_field].sum()
            base["sink_attraction_base"] = grouped.reindex(base.index).fillna(0.0)
        else:
            # Weighted POI counts
            def weight_row(r: pd.Series) -> float:
                typ = str(r.get("poi_type", r.get("type", r.get("amenity", "")))).lower()
                for key, w in POI_WEIGHTS.items():
                    if key in typ:
                        return float(w)
                # Fallback category
                cat = _poi_category(r)
                # Map category to approximate weight baseline
                cat_w = {"work": 3, "education": 4, "health": 5, "leisure": 1, "transport": 5}.get(cat, 2)
                return float(cat_w)
            pj_in["poi_weight"] = pj_in.apply(weight_row, axis=1)
            grouped = pj_in.groupby("node")["poi_weight"].sum()
            base["sink_attraction_base"] = grouped.reindex(base.index).fillna(0.0)

    # Time-of-day scaling
    out = base.copy()
    out["sink_attraction_morning"] = out["sink_attraction_base"] * TIME_WEIGHTS["Morning rush"]["work"]
    out["sink_attraction_day"] = out["sink_attraction_base"] * TIME_WEIGHTS["Day"]["work"]
    out["sink_attraction_evening"] = out["sink_attraction_base"] * max(TIME_WEIGHTS["Evening rush"].values())
    out["sink_attraction_night"] = out["sink_attraction_base"] * max(TIME_WEIGHTS["Night"].values())
    return out


# -----------------------------
# 5) Supernode rollups
# -----------------------------

def rollup_to_supernodes(G, node_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate node-level stats to supernodes using 'members'."""
    # Determine supernodes and their member sets
    super_to_members: Dict[Any, List[Any]] = {}
    for n, d in G.nodes(data=True):
        if d.get("is_supernode"):
            mem = d.get("members")
            members = list(mem) if isinstance(mem, (list, tuple, set)) and len(mem) > 0 else [n]
            super_to_members[n] = members

    cols = [c for c in node_df.columns if c not in {"node"}]
    rows: List[Dict[str, Any]] = []
    for sn, mems in super_to_members.items():
        sub = node_df.loc[node_df.index.intersection(pd.Index(mems))]
        agg = {c: float(sub[c].sum()) for c in cols if c in sub.columns}
        agg["supernode"] = sn
        rows.append(agg)
    out = pd.DataFrame(rows).set_index("supernode") if rows else pd.DataFrame(columns=["supernode"]).set_index("supernode")
    return out


# -----------------------------
# 6) Impedance and gravity flows
# -----------------------------

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import radians, sin, cos, asin, sqrt
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * R * asin(sqrt(a))


def impedance_matrix(G, metric: str = "time", speed_kmh: float = 30.0) -> pd.DataFrame:
    """Pairwise impedance between supernodes: minutes (time) or distance (km)."""
    # Collect supernode centroids
    supernodes = [n for n, d in G.nodes(data=True) if d.get("is_supernode")]
    if not supernodes:
        return pd.DataFrame()

    # Precompute node coordinates
    coords: Dict[Any, Tuple[float, float]] = {}
    for n, d in G.nodes(data=True):
        x, y = d.get("x"), d.get("y")
        if x is None or y is None:
            continue
        coords[n] = (float(x), float(y))

    # Compute centroids as mean of members
    centroids: Dict[Any, Tuple[float, float]] = {}
    for sn in supernodes:
        d = G.nodes[sn]
        mem = d.get("members")
        mems = list(mem) if isinstance(mem, (list, tuple, set)) and len(mem) > 0 else [sn]
        xs, ys = [], []
        for m in mems:
            if m in coords:
                xs.append(coords[m][0])
                ys.append(coords[m][1])
        if xs and ys:
            centroids[sn] = (float(np.mean(xs)), float(np.mean(ys)))
        else:
            centroids[sn] = coords.get(sn, (None, None))

    # If metric is time, convert distances to minutes by speed; else report km
    tau = pd.DataFrame(index=supernodes, columns=supernodes, dtype=float)
    for i in supernodes:
        for j in supernodes:
            if i == j:
                tau.loc[i, j] = 0.0
                continue
            xi, yi = centroids[i]
            xj, yj = centroids[j]
            if xi is None or yi is None or xj is None or yj is None:
                tau.loc[i, j] = np.nan
                continue
            dist_km = _haversine_km(yi, xi, yj, xj)
            if metric == "time":
                tau.loc[i, j] = (dist_km / max(1e-3, float(speed_kmh))) * 60.0
            else:
                tau.loc[i, j] = dist_km
    return tau


def expected_flows_gravity(
    supernode_stats: pd.DataFrame,
    tau: pd.DataFrame,
    time_bin: str,
    k: float = 1.0,
    beta: float = 0.15,
    form: str = "exp",
) -> pd.DataFrame:
    """E_ij = k * S_i * A_j(bin) * f(tau_ij)."""
    if supernode_stats.empty or tau.empty:
        return pd.DataFrame()
    S = supernode_stats["source_population"].astype(float).values
    col_map = {
        "Morning rush": "sink_attraction_morning",
        "Day": "sink_attraction_day",
        "Evening rush": "sink_attraction_evening",
        "Night": "sink_attraction_night",
    }
    a_col = col_map.get(time_bin)
    if a_col not in supernode_stats.columns:
        return pd.DataFrame()
    A = supernode_stats[a_col].astype(float).values
    nodes = list(supernode_stats.index)
    T = tau.loc[nodes, nodes].values.astype(float)
    if form == "exp":
        F = np.exp(-beta * T)
    else:
        T_safe = np.where(T <= 0, np.nan, T)
        F = np.power(T_safe, -beta)
        F = np.nan_to_num(F, nan=0.0, posinf=0.0, neginf=0.0)
    E = k * np.outer(S, A) * F
    # zero diagonal
    np.fill_diagonal(E, 0.0)
    return pd.DataFrame(E, index=nodes, columns=nodes)


# -----------------------------
# 7) Calibration with SCATS (optional stub)
# -----------------------------

def calibrate_gravity_with_scats(
    E_ij_bin: pd.DataFrame,
    scats_df: pd.DataFrame,
    mapping: Dict[Any, Any],
    time_bin: str,
) -> Dict[str, float]:
    """Simple placeholder calibration returning defaults. Extend as needed."""
    # TODO: Map SCATS to supernode in/out and fit (k, beta). For now, return identity.
    return {"k": 1.0, "beta": 0.15}


# -----------------------------
# 8) Orchestration
# -----------------------------

def estimate_sources_sinks_and_flows(
    G,
    census_path: Optional[Path | str] = None,
    landuse_path: Optional[Path | str] = None,
    pois_jobs_path: Optional[Path | str] = None,
    scats_df: Optional[pd.DataFrame] = None,
    time_bins: Optional[Dict[str, Dict[str, str]]] = None,
    crs_projected: str = "EPSG:2157",
) -> Dict[str, Any]:
    """
    Returns dict with keys: 'node_stats', 'supernode_stats', 'tau', 'E_by_bin'.
    Also writes key stats back to G supernodes.
    """
    # Build catchments
    catch = build_node_catchments(G, method="voronoi", buffer_m=250, crs_projected=crs_projected)

    # Load and compute sources
    census = load_census_geometries(census_path) if census_path else None  # type: ignore[arg-type]
    resmask = load_landuse_mask(landuse_path) if landuse_path else None  # type: ignore[arg-type]
    if census is not None:
        node_sources = dasymetric_allocate_population(census, resmask, catch)
    else:
        # Fallback: zeros
        node_sources = pd.DataFrame(index=catch["node"], data={"source_population": 0.0, "source_density": 0.0})
        node_sources.index.name = "node"

    # Load and compute sinks
    pois = load_pois_or_jobs(pois_jobs_path) if pois_jobs_path else None  # type: ignore[arg-type]
    node_sinks = compute_sink_attraction(pois, catch)

    # Merge node-level stats
    node_stats = node_sources.join(node_sinks, how="outer").fillna(0.0)
    node_stats.index.name = "node"

    # Roll up to supernodes
    super_stats = rollup_to_supernodes(G, node_stats)
    if not super_stats.empty:
        # Write back key fields to graph nodes
        for sn, row in super_stats.iterrows():
            d = G.nodes[sn]
            d["source_population"] = float(row.get("source_population", 0.0))
            d["source_density"] = float(row.get("source_density", 0.0))
            d["sink_attraction_morning"] = float(row.get("sink_attraction_morning", 0.0))
            d["sink_attraction_day"] = float(row.get("sink_attraction_day", 0.0))
            d["sink_attraction_evening"] = float(row.get("sink_attraction_evening", 0.0))
            d["sink_attraction_night"] = float(row.get("sink_attraction_night", 0.0))

    # Impedance matrix
    tau = impedance_matrix(G, metric="time", speed_kmh=30.0)

    # Expected flows by bin
    bins = list((time_bins or DEFAULT_TIME_BINS).keys())
    E_by_bin: Dict[str, pd.DataFrame] = {}
    for b in bins:
        if super_stats.empty or tau.empty:
            E_by_bin[b] = pd.DataFrame()
            continue
        E = expected_flows_gravity(super_stats, tau, time_bin=b, k=1.0, beta=0.15, form="exp")
        E_by_bin[b] = E

    # Store expected in/out flow summaries on supernodes for viz
    for sn in super_stats.index:
        for b, E in E_by_bin.items():
            if E.empty or sn not in E.index:
                continue
            outflow = float(E.loc[sn].sum())
            inflow = float(E[sn].sum())
            d = G.nodes[sn]
            key_out = f"expected_outflow_{b.split()[0].lower()}"  # e.g., Morning -> expected_outflow_morning
            key_in = f"expected_inflow_{b.split()[0].lower()}"
            d[key_out] = outflow
            d[key_in] = inflow

    return {
        "node_stats": node_stats,
        "supernode_stats": super_stats,
        "tau": tau,
        "E_by_bin": E_by_bin,
    }


__all__ = [
    "load_census_geometries",
    "load_landuse_mask",
    "load_pois_or_jobs",
    "build_node_catchments",
    "dasymetric_allocate_population",
    "compute_sink_attraction",
    "rollup_to_supernodes",
    "impedance_matrix",
    "expected_flows_gravity",
    "calibrate_gravity_with_scats",
    "estimate_sources_sinks_and_flows",
    "DEFAULT_TIME_BINS",
    "POI_WEIGHTS",
]


