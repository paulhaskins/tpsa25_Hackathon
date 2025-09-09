from pathlib import Path
import osmnx as ox
import networkx as nx


def build_graph(place: str) -> nx.MultiDiGraph:
    """Build a drivable street graph for a place using OSMnx."""
    G = ox.graph_from_place(place, network_type="drive")
    return G


def save_graphml(G: nx.MultiDiGraph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(G, filepath=str(path))


def load_graphml(path: Path) -> nx.MultiDiGraph:
    return ox.load_graphml(filepath=str(path))


