"""Folium visualisation utilities for traffic graphs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

import folium
import numpy as np
import networkx as nx


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


def save_folium_flow_map(G: nx.MultiDiGraph, html_path: Path | str, width: int = 2) -> None:
    """Plot graph on a Folium map, color edges by flow intensity, mark supernodes.

    - Edges: colored by mean of 'flow_series' (or a fallback using capacity).
    - Supernodes (node attribute is_supernode=True): red markers.
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

    # Mark supernodes
    for n, d in G.nodes(data=True):
        if d.get("is_supernode"):
            x, y = d.get("x"), d.get("y")
            if x is None or y is None:
                continue
            folium.CircleMarker(
                location=(y, x),
                radius=5,
                color="red",
                fill=True,
                fill_color="red",
                fill_opacity=0.9,
                popup=str(n),
            ).add_to(fmap)

    fmap.save(str(html_path))


__all__ = ["save_folium_flow_map"]

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


