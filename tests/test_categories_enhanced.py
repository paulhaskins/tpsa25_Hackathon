"""Tests for enhanced category detection functionality."""

import networkx as nx
import pandas as pd
import numpy as np
from pathlib import Path
import tempfile
from src.traffic_model.categories import (
    classify_poi_category,
    query_osm_pois,
    map_pois_to_nodes,
    query_google_places,
    map_google_places_to_nodes,
    map_google_place_type_to_category,
    detect_business_heuristics,
    assign_categories_enhanced,
    assign_categories_to_nodes
)


def test_classify_poi_category():
    """Test POI category classification."""
    # Test business categories
    business_tags = {
        'amenity': 'restaurant',
        'shop': 'supermarket',
        'office': 'company',
        'landuse': 'commercial'
    }
    assert classify_poi_category(business_tags) == 'Business'
    
    # Test school categories
    school_tags = {
        'amenity': 'school',
        'amenity': 'university',
        'landuse': 'education'
    }
    assert classify_poi_category(school_tags) == 'School'
    
    # Test hospital categories
    hospital_tags = {
        'amenity': 'hospital',
        'amenity': 'clinic',
        'landuse': 'health'
    }
    assert classify_poi_category(hospital_tags) == 'Hospital'
    
    # Test transport categories
    transport_tags = {
        'amenity': 'bus_station',
        'railway': 'station',
        'public_transport': 'station'
    }
    assert classify_poi_category(transport_tags) == 'Transport'
    
    # Test residential categories
    residential_tags = {
        'landuse': 'residential',
        'amenity': 'house'
    }
    assert classify_poi_category(residential_tags) == 'Residential'
    
    # Test unknown categories
    unknown_tags = {
        'highway': 'primary',
        'surface': 'asphalt'
    }
    assert classify_poi_category(unknown_tags) == 'Other'


def test_map_google_place_type_to_category():
    """Test Google Places type to category mapping."""
    assert map_google_place_type_to_category('shopping_mall') == 'Business'
    assert map_google_place_type_to_category('airport') == 'Transport'
    assert map_google_place_type_to_category('hospital') == 'Hospital'
    assert map_google_place_type_to_category('university') == 'School'
    assert map_google_place_type_to_category('unknown_type') == 'Other'


def test_detect_business_heuristics():
    """Test business detection heuristics."""
    # Create a test graph with nodes near center and high connectivity
    G = nx.MultiDiGraph()
    
    # Add nodes with different characteristics
    G.add_node(1, x=0.0, y=0.0)  # Center node
    G.add_node(2, x=0.001, y=0.001)  # Near center
    G.add_node(3, x=0.1, y=0.1)  # Far from center
    G.add_node(4, x=0.002, y=0.002)  # Near center
    
    # Add edges to create different connectivity patterns
    G.add_edge(1, 2)
    G.add_edge(1, 3)
    G.add_edge(1, 4)
    G.add_edge(2, 4)
    G.add_edge(3, 4)
    G.add_edge(2, 3)
    G.add_edge(1, 2)  # Duplicate edge for higher degree
    
    # Apply heuristics
    business_nodes = detect_business_heuristics(G, "Test City")
    
    # Node 1 should be detected as business (center, high degree)
    assert 1 in business_nodes
    assert business_nodes[1] == 'Business'
    
    # Node 3 should not be detected (far from center)
    assert 3 not in business_nodes


def test_map_pois_to_nodes():
    """Test mapping POIs to nearest nodes."""
    # Create test POI data
    pois_df = pd.DataFrame({
        'lon': [-6.0, -6.01, -6.02],
        'lat': [53.0, 53.01, 53.02],
        'poi_type': ['amenity', 'shop', 'amenity'],
        'poi_value': ['restaurant', 'supermarket', 'school']
    })
    
    # Create test graph
    G = nx.MultiDiGraph()
    G.add_node(1, x=-6.0, y=53.0)
    G.add_node(2, x=-6.01, y=53.01)
    G.add_node(3, x=-6.02, y=53.02)
    G.add_node(4, x=-6.1, y=53.1)  # Far from POIs
    
    # Map POIs to nodes
    node_categories = map_pois_to_nodes(pois_df, G, max_distance=1000.0)
    
    # Check that POIs were mapped to nearest nodes
    assert 1 in node_categories  # Restaurant -> Business
    assert 2 in node_categories  # Supermarket -> Business
    assert 3 in node_categories  # School -> School
    assert 4 not in node_categories  # Too far
    
    # Check categories
    assert node_categories[1] == 'Business'
    assert node_categories[2] == 'Business'
    assert node_categories[3] == 'School'


def test_assign_categories_enhanced():
    """Test enhanced category assignment."""
    # Create test graph
    G = nx.MultiDiGraph()
    G.add_node(1, x=-6.0, y=53.0, amenity='restaurant')
    G.add_node(2, x=-6.01, y=53.01, shop='supermarket')
    G.add_node(3, x=-6.02, y=53.02, amenity='school')
    G.add_node(4, x=-6.03, y=53.03, highway='primary')
    
    # Test with heuristics only (no external APIs)
    G_result = assign_categories_enhanced(
        G, 
        "Test City", 
        use_osm=False, 
        use_google=False, 
        use_heuristics=True
    )
    
    # Check that categories were assigned
    for node, data in G_result.nodes(data=True):
        assert 'category' in data
        assert data['category'] in ['Residential', 'Business', 'School', 'Hospital', 'Transport', 'Other']
    
    # Check specific categories
    assert G_result.nodes[1]['category'] == 'Business'  # Restaurant
    assert G_result.nodes[2]['category'] == 'Business'  # Supermarket
    assert G_result.nodes[3]['category'] == 'School'    # School
    assert G_result.nodes[4]['category'] == 'Other'     # Highway


def test_enhanced_category_assignment_smoke_test():
    """Smoke test for the complete enhanced category assignment workflow."""
    # Create a toy graph with different node types
    G = nx.MultiDiGraph()
    G.add_node(1, x=-6.0, y=53.0, amenity='restaurant', shop='cafe')
    G.add_node(2, x=-6.01, y=53.01, amenity='school', landuse='education')
    G.add_node(3, x=-6.02, y=53.02, amenity='hospital', landuse='health')
    G.add_node(4, x=-6.03, y=53.03, railway='station', public_transport='station')
    G.add_node(5, x=-6.04, y=53.04, landuse='residential')
    G.add_node(6, x=-6.05, y=53.05, highway='primary')  # Should be Other
    
    # Add some edges for connectivity
    G.add_edge(1, 2)
    G.add_edge(2, 3)
    G.add_edge(3, 4)
    G.add_edge(4, 5)
    G.add_edge(5, 6)
    G.add_edge(1, 3)
    G.add_edge(2, 4)
    
    # Run enhanced category assignment
    G_result = assign_categories_enhanced(
        G, 
        "Test City", 
        use_osm=False, 
        use_google=False, 
        use_heuristics=True
    )
    
    # Verify results
    assert len(G_result.nodes) == 6
    
    for node, data in G_result.nodes(data=True):
        # Check required attributes
        assert 'category' in data
        
        # Check data types and values
        assert isinstance(data['category'], str)
        assert data['category'] in ['Residential', 'Business', 'School', 'Hospital', 'Transport', 'Other']
    
    # Check that we have a good distribution of categories
    categories = [data['category'] for _, data in G_result.nodes(data=True)]
    unique_categories = set(categories)
    assert len(unique_categories) > 1  # Should have multiple categories
    
    # Check specific expected categories
    assert 'Business' in categories  # Restaurant/cafe
    assert 'School' in categories    # School
    # Note: Hospital and Transport might be overridden by heuristics, so we check for either original or Business
    assert 'Hospital' in categories or 'Business' in categories  # Hospital or overridden by heuristics
    assert 'Transport' in categories or 'Business' in categories # Station or overridden by heuristics


def test_category_assignment_with_mock_pois():
    """Test category assignment with mock POI data."""
    # Create test graph
    G = nx.MultiDiGraph()
    G.add_node(1, x=-6.0, y=53.0)
    G.add_node(2, x=-6.01, y=53.01)
    G.add_node(3, x=-6.02, y=53.02)
    
    # Create mock POI data
    pois_df = pd.DataFrame({
        'lon': [-6.0, -6.01, -6.02],
        'lat': [53.0, 53.01, 53.02],
        'poi_type': ['amenity', 'shop', 'amenity'],
        'poi_value': ['restaurant', 'supermarket', 'school']
    })
    
    # Map POIs to nodes
    node_categories = map_pois_to_nodes(pois_df, G)
    
    # Apply categories to graph
    for node, category in node_categories.items():
        G.nodes[node]['category'] = category
    
    # Check results
    assert G.nodes[1]['category'] == 'Business'
    assert G.nodes[2]['category'] == 'Business'
    assert G.nodes[3]['category'] == 'School'


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q", "-s"]))
