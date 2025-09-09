import networkx as nx
from traffic_model import detect_single_connection_neighborhoods, collapse_neighborhoods_to_supernodes


def small_bridge_graph():
    # Two clusters connected by a single bridge edge (2-3)
    G = nx.MultiDiGraph()
    # cluster A
    G.add_node(1, x=0, y=0)
    G.add_node(2, x=0.001, y=0)
    G.add_edge(1, 2, flow_series=[10]*24)
    G.add_edge(2, 1, flow_series=[5]*24)
    # cluster B
    G.add_node(3, x=0.01, y=0)
    G.add_node(4, x=0.011, y=0)
    G.add_edge(3, 4, flow_series=[3]*24)
    G.add_edge(4, 3, flow_series=[7]*24)
    # bridge
    G.add_edge(2, 3, flow_series=[1]*24)
    G.add_edge(3, 2, flow_series=[1]*24)
    return G


def test_detect_and_collapse_single_connection():
    G = small_bridge_graph()
    neighs = detect_single_connection_neighborhoods(G)
    assert len(neighs) >= 1
    Gc = collapse_neighborhoods_to_supernodes(G, neighs)
    # Expect at least one supernode
    assert any(d.get("is_supernode") for _, d in Gc.nodes(data=True))
    # Supernode should carry external flow summary
    supers = [d for _, d in Gc.nodes(data=True) if d.get("is_supernode")]
    assert "external_flow_series" in supers[0]
    assert len(supers[0]["external_flow_series"]) == 24


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q", "-s"]))


