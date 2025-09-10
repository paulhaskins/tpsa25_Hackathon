"""Tests for capacity computation functionality."""

import networkx as nx
from traffic_model.capacity import compute_edge_capacity, attach_capacity_to_graph


def test_compute_edge_capacity():
    """Test edge capacity computation."""
    # Test basic calculation
    capacity = compute_edge_capacity(length_m=100.0, lanes=2, car_length=4.5)
    expected = int(100.0 / 4.5) * 2  # 22 * 2 = 44
    assert capacity == expected
    
    # Test edge cases
    assert compute_edge_capacity(0, 1) == 0
    assert compute_edge_capacity(10, 0) == 0
    assert compute_edge_capacity(10, 1, 0) == 0


def test_attach_capacity_to_graph():
    """Test attaching capacity to graph edges."""
    G = nx.MultiDiGraph()
    G.add_node(1, x=0, y=0)
    G.add_node(2, x=0.001, y=0.001)
    G.add_edge(1, 2, length=100.0, lanes=2)
    
    G_with_capacity = attach_capacity_to_graph(G)
    
    # Check that capacity was added
    for u, v, k, data in G_with_capacity.edges(keys=True, data=True):
        assert 'capacity' in data
        assert data['capacity'] > 0


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q", "-s"]))
