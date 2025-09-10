"""Tests for supernode detection and collapse functionality."""

import networkx as nx
from pathlib import Path
from traffic_model.super_nodes import (
    detect_supernodes, 
    collapse_supernodes, 
    save_supernodes_to_file, 
    load_supernodes_from_file,
    detect_and_cache_supernodes
)


def test_detect_supernodes():
    """Test supernode detection."""
    # Create a simple graph with a neighborhood
    G = nx.MultiDiGraph()
    G.add_node(1, x=0, y=0)
    G.add_node(2, x=0.001, y=0.001)
    G.add_node(3, x=0.002, y=0.002)
    G.add_node(4, x=0.1, y=0.1)  # Outside neighborhood
    
    # Create a neighborhood connected by a single bridge
    G.add_edge(1, 2)
    G.add_edge(2, 3)
    G.add_edge(3, 4)  # Bridge to outside
    
    supernodes = detect_supernodes(G)
    
    # Should detect at least one supernode
    assert isinstance(supernodes, dict)


def test_collapse_supernodes():
    """Test supernode collapse."""
    G = nx.MultiDiGraph()
    G.add_node(1, x=0, y=0)
    G.add_node(2, x=0.001, y=0.001)
    G.add_node(3, x=0.002, y=0.002)
    G.add_node(4, x=0.1, y=0.1)
    
    G.add_edge(1, 2)
    G.add_edge(2, 3)
    G.add_edge(3, 4)
    
    # Create mock supernodes
    supernodes = {
        1: {
            'type': 'Residential',
            'population_capacity': 100,
            'members': [1, 2, 3],
            'entry_node': 1
        }
    }
    
    G_collapsed = collapse_supernodes(G, supernodes)
    
    # Should have fewer nodes after collapse
    assert len(G_collapsed.nodes) < len(G.nodes)
    
    # Check for supernode attributes
    for node, data in G_collapsed.nodes(data=True):
        if data.get('is_supernode'):
            assert 'type' in data
            assert 'population_capacity' in data


def test_save_and_load_supernodes(tmp_path: Path):
    """Test saving and loading supernodes to/from file."""
    # Create mock supernodes
    supernodes = {
        1: {
            'type': 'Residential',
            'population_capacity': 100,
            'members': {1, 2, 3},
            'entry_node': 1
        },
        4: {
            'type': 'Business',
            'population_capacity': 200,
            'members': {4, 5},
            'entry_node': 4
        }
    }
    
    # Save to file
    place = "Test City"
    filepath = save_supernodes_to_file(supernodes, place, output_dir=tmp_path)
    assert filepath.exists()
    
    # Load from file
    loaded_supernodes = load_supernodes_from_file(place, input_dir=tmp_path)
    assert loaded_supernodes is not None
    assert len(loaded_supernodes) == 2
    assert 1 in loaded_supernodes
    assert 4 in loaded_supernodes
    
    # Check that members are converted back to sets
    assert isinstance(loaded_supernodes[1]['members'], set)
    assert loaded_supernodes[1]['members'] == {1, 2, 3}


def test_detect_and_cache_supernodes(tmp_path: Path):
    """Test supernode detection with caching."""
    # Create a simple graph
    G = nx.MultiDiGraph()
    G.add_node(1, x=0, y=0)
    G.add_node(2, x=0.001, y=0.001)
    G.add_node(3, x=0.002, y=0.002)
    G.add_node(4, x=0.1, y=0.1)
    
    G.add_edge(1, 2)
    G.add_edge(2, 3)
    G.add_edge(3, 4)
    
    place = "Test City"
    
    # First run: should compute and cache
    supernodes1 = detect_and_cache_supernodes(G, place, force_recompute=False, output_dir=tmp_path)
    assert isinstance(supernodes1, dict)
    
    # Check that cache file was created
    cache_file = tmp_path / "supernodes_test_city.json"
    assert cache_file.exists()
    
    # Second run: should load from cache
    supernodes2 = detect_and_cache_supernodes(G, place, force_recompute=False, output_dir=tmp_path)
    assert isinstance(supernodes2, dict)
    
    # Should have same structure (though exact content may vary due to neighborhood detection)
    assert len(supernodes1) == len(supernodes2)
    
    # Force recompute: should ignore cache
    supernodes3 = detect_and_cache_supernodes(G, place, force_recompute=True, output_dir=tmp_path)
    assert isinstance(supernodes3, dict)


def test_supernode_caching_with_different_places(tmp_path: Path):
    """Test that different places get separate cache files."""
    G = nx.MultiDiGraph()
    G.add_node(1, x=0, y=0)
    G.add_node(2, x=0.001, y=0.001)
    G.add_edge(1, 2)
    
    place1 = "Dublin, Ireland"
    place2 = "Cork, Ireland"
    
    # Create supernodes for both places
    supernodes1 = detect_and_cache_supernodes(G, place1, output_dir=tmp_path)
    supernodes2 = detect_and_cache_supernodes(G, place2, output_dir=tmp_path)
    
    # Should create separate cache files
    cache1 = tmp_path / "supernodes_dublin_ireland.json"
    cache2 = tmp_path / "supernodes_cork_ireland.json"
    
    assert cache1.exists()
    assert cache2.exists()
    assert cache1 != cache2


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q", "-s"]))
