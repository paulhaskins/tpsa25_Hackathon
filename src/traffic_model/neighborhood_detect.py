"""Neighbourhood detection utilities.

Placeholder functions for detecting closed neighbourhoods that can be collapsed
into supernodes during simplification.
"""

import networkx as nx


def detect_neighborhoods(G: nx.Graph) -> list[list[int]]:
    """Return a list of neighborhoods (each as a list of node ids).

    For now, this is a stub that returns connected components of the undirected
    version for demonstration.
    """
    undirected = nx.Graph(G)
    return [list(c) for c in nx.connected_components(undirected)]


