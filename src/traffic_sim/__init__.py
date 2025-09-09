"""Minimal traffic flow simulation package.

Modules:
- graph_loader: Load OSM or build a synthetic graph and tag supernodes
- capacity: Compute edge capacities and initialize state
- demand: Build schedules and inject source demand into node buffers
- route: Precompute sink distances and compute transition probabilities
- simulate: Run per-step updates and multi-step runs
- viz: Render folium maps of saturation
- cli: Typer CLI to run demos

The package is intentionally small and self-contained for hackathon demos.
"""

from .graph_loader import load_osm, make_synthetic, tag_supernodes  # noqa: F401
from .capacity import edge_capacity  # noqa: F401
from .demand import build_schedules, inject_sources  # noqa: F401
from .route import precompute_sink_distances, transition_probs  # noqa: F401
from .simulate import run, step  # noqa: F401
from .viz import to_folium  # noqa: F401

__all__ = [
    "load_osm",
    "make_synthetic",
    "tag_supernodes",
    "edge_capacity",
    "build_schedules",
    "inject_sources",
    "precompute_sink_distances",
    "transition_probs",
    "step",
    "run",
    "to_folium",
]


