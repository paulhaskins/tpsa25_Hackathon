from __future__ import annotations

from typing import Dict

import folium
import networkx as nx


def _saturation_color(s: float) -> str:
    s = max(0.0, min(1.5, s)) / 1.5
    # blue (low) -> red (high)
    r = int(255 * s)
    b = int(255 * (1 - s))
    g = 50
    return f"#{r:02x}{g:02x}{b:02x}"


def to_folium(G: nx.DiGraph, t_label: str, out_html: str) -> None:
    """Render a folium map with edges colored by saturation r/R and supernodes."""
    # Center
    xs = [float(d.get("x", 0.0)) for _, d in G.nodes(data=True)]
    ys = [float(d.get("y", 0.0)) for _, d in G.nodes(data=True)]
    center = (sum(ys) / max(len(ys), 1), sum(xs) / max(len(xs), 1))
    m = folium.Map(location=center, zoom_start=14, tiles="cartodbpositron")

    # Edges
    for u, v, d in G.edges(data=True):
        uxy = (float(G.nodes[u].get("y", 0.0)), float(G.nodes[u].get("x", 0.0)))
        vxy = (float(G.nodes[v].get("y", 0.0)), float(G.nodes[v].get("x", 0.0)))
        R = float(d.get("R", 1.0))
        r = float(d.get("r", 0.0))
        sat = r / max(R, 1e-6)
        color = _saturation_color(sat)
        folium.PolyLine([uxy, vxy], color=color, weight=4, opacity=0.8).add_to(m)

    # Nodes
    for n, data in G.nodes(data=True):
        xy = (float(data.get("y", 0.0)), float(data.get("x", 0.0)))
        ntype = data.get("type", "junction")
        buffer = float(data.get("buffer", 0.0))
        injected = float(data.get("last_injected", 0.0))
        arrivals = float(data.get("last_arrivals", 0.0))
        cum_inj = float(data.get("cum_injected", 0.0))
        cum_arr = float(data.get("cum_arrivals", 0.0))
        if ntype == "residential":
            size = 6 + 0.02 * float(data.get("H", 100.0))
            tip = f"res {n} | H={data.get('H',0)} | buf={buffer:.1f} | inj={injected:.1f} | cum_inj={cum_inj:.1f}"
            folium.CircleMarker(xy, radius=size / 10, color="#3366cc", fill=True, fill_opacity=0.7, tooltip=tip).add_to(m)
        elif ntype == "sink":
            size = 6 + 0.02 * float(data.get("W", 100.0))
            tip = f"sink {n} | W={data.get('W',0)} | buf={buffer:.1f} | arr={arrivals:.1f} | cum_arr={cum_arr:.1f}"
            folium.CircleMarker(xy, radius=size / 10, color="#33cc66", fill=True, fill_opacity=0.7, tooltip=tip).add_to(m)
        else:
            tip = f"node {n} | buf={buffer:.1f}"
            folium.CircleMarker(xy, radius=3, color="#888888", fill=True, fill_opacity=0.5, tooltip=tip).add_to(m)

    folium.map.LayerControl().add_to(m)
    folium.map.Marker(center, tooltip=f"t={t_label}").add_to(m)
    m.save(out_html)


