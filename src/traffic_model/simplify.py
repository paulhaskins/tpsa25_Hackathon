"""Graph simplification into supernodes using neighborhood detection."""

import networkx as nx
from .neighborhood import detect_single_connection_neighborhoods, collapse_neighborhoods_to_supernodes


def simplify_graph(G: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Detect single-connection neighborhoods and collapse them into supernodes."""
    neighs = detect_single_connection_neighborhoods(G)
    if not neighs:
        return G
    return collapse_neighborhoods_to_supernodes(G, neighs)


