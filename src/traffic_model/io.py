"""I/O helpers for saving/loading graphs and data (placeholder)."""

from pathlib import Path
import osmnx as ox
import networkx as nx


def save_graph(G: nx.MultiDiGraph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(G, filepath=str(path))


def load_graph(path: Path) -> nx.MultiDiGraph:
    return ox.load_graphml(filepath=str(path))


