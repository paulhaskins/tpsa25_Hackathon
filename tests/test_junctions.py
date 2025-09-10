"""Tests for junction efficiency functionality."""

import networkx as nx
from traffic_model.junctions import compute_junction_efficiency, annotate_junctions


def test_compute_junction_efficiency():
    """Test junction efficiency computation."""
    G = nx.MultiDiGraph()
    G.add_node(1, x=0, y=0)
    G.add_node(2, x=0.001, y=0.001)
    G.add_node(3, x=0.002, y=0.002)
    G.add_node(4, x=0.003, y=0.003)
    
    # Test simple intersection (degree 2)
    G.add_edge(1, 2)
    G.add_edge(2, 1)
    efficiency = compute_junction_efficiency(G, 2)
    assert efficiency == 1.0
    
    # Test T-junction (degree 3)
    G.add_edge(2, 3)
    efficiency = compute_junction_efficiency(G, 2)
    assert efficiency == 0.9
    
    # Test 4-way intersection (degree 4)
    G.add_edge(2, 4)
    efficiency = compute_junction_efficiency(G, 2)
    assert efficiency == 0.8
    
    # Test non-existent node
    efficiency = compute_junction_efficiency(G, 999)
    assert efficiency == 1.0


def test_annotate_junctions():
    """Test junction annotation."""
    G = nx.MultiDiGraph()
    G.add_node(1, x=0, y=0)
    G.add_node(2, x=0.001, y=0.001)
    G.add_node(3, x=0.002, y=0.002)
    G.add_node(4, x=0.003, y=0.003)
    
    # Create a junction
    G.add_edge(1, 2)
    G.add_edge(2, 3)
    G.add_edge(2, 4)
    
    G_annotated = annotate_junctions(G)
    
    # Check that efficiency was added to junction nodes
    for node, data in G_annotated.nodes(data=True):
        assert 'efficiency' in data
        assert 0 < data['efficiency'] <= 1.0


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q", "-s"]))
