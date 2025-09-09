from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Optional

import typer

from .graph_loader import load_osm, make_synthetic, tag_supernodes
from .capacity import edge_capacity
from .demand import build_schedules, inject_sources
from .simulate import run
from .viz import to_folium

import networkx as nx
import yaml


app = typer.Typer(add_completion=False)


def _ensure_outputs() -> Path:
    out = Path("outputs")
    out.mkdir(parents=True, exist_ok=True)
    return out


def _load_config(path: Optional[str]) -> dict:
    if path and Path(path).exists():
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {
        "place": "Dublin, Ireland",
        "steps": 24,
        "dt_minutes": 60,
        "beta": 0.5,
        "alpha": 1.0,
        "n_residential": 5,
        "n_sinks": 3,
    }


def _setup_graph(place: Optional[str], n_residential: int, n_sinks: int) -> nx.DiGraph:
    G: nx.DiGraph
    if place:
        try:
            G = load_osm(place)
        except Exception:
            G = make_synthetic()
    else:
        G = make_synthetic()
    tag_supernodes(G, n_residential=n_residential, n_sinks=n_sinks)
    edge_capacity(G)
    return G


@app.command()
def demo(config: Optional[str] = typer.Option(None, help="Path to YAML config")) -> None:
    cfg = _load_config(config)
    out = _ensure_outputs()
    G = _setup_graph(cfg.get("place"), cfg.get("n_residential", 5), cfg.get("n_sinks", 3))

    params = {"beta": cfg.get("beta", 0.5), "alpha": cfg.get("alpha", 1.0), "dt_minutes": cfg.get("dt_minutes", 60)}
    schedules = build_schedules(cfg)
    steps = int(cfg.get("steps", 24))
    start = dt.datetime(2024, 1, 1, 6, 0, 0)

    t = start
    for step_idx in range(steps):
        inject_sources(G, t, schedules)
        # run one step and render
        _ = run(G, params, schedules, steps=1, start_time=t)
        to_folium(G, f"{t.hour:02d}:00", str(out / f"map_t{step_idx:02d}.html"))
        t = t + dt.timedelta(minutes=int(params["dt_minutes"]))


@app.command()
def osm(place: str = typer.Option("Dublin, Ireland", help="Place name for OSM"), steps: int = 12, beta: float = 0.5, alpha: float = 1.0) -> None:
    out = _ensure_outputs()
    G = _setup_graph(place, n_residential=5, n_sinks=3)
    params = {"beta": beta, "alpha": alpha, "dt_minutes": 60}
    schedules = build_schedules({})
    start = dt.datetime(2024, 1, 1, 6, 0, 0)

    t = start
    for step_idx in range(steps):
        inject_sources(G, t, schedules)
        _ = run(G, params, schedules, steps=1, start_time=t)
        to_folium(G, f"{t.hour:02d}:00", str(out / f"map_t{step_idx:02d}.html"))
        t = t + dt.timedelta(minutes=int(params["dt_minutes"]))


def main() -> None:
    app()


if __name__ == "__main__":
    main()


