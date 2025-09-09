import networkx as nx
from traffic_model import generate_synthetic_flows


def simple_graph():
    G = nx.MultiDiGraph()
    G.add_node(1, x=-6.0, y=53.0)
    G.add_node(2, x=-6.01, y=53.01)
    G.add_edge(1, 2, capacity=3600)
    G.add_edge(2, 1, lanes=1)  # capacity inferred 1800
    return G


def test_generate_synthetic_flows():
    G = simple_graph()
    generate_synthetic_flows(G, seed=0)
    for u, v, k, d in G.edges(keys=True, data=True):
        assert "flow_series" in d
        assert isinstance(d["flow_series"], list)
        assert len(d["flow_series"]) == 24
        assert all(x >= 0 for x in d["flow_series"])  # non-negative


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q", "-s"]))


