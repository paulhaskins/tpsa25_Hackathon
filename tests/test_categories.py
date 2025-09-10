"""Tests for node category classification functionality."""

import networkx as nx
from traffic_model.categories import classify_poi_category, assign_categories_to_nodes


def test_classify_poi_category():
    """Test POI category classification."""
    # Test residential
    residential_tags = {'landuse': 'residential'}
    assert classify_poi_category(residential_tags) == "Residential"
    
    # Test business
    business_tags = {'amenity': 'shop'}
    assert classify_poi_category(business_tags) == "Business"
    
    # Test transport
    transport_tags = {'public_transport': 'station'}
    assert classify_poi_category(transport_tags) == "Transport"
    
    # Test school
    school_tags = {'amenity': 'school'}
    assert classify_poi_category(school_tags) == "School"
    
    # Test hospital
    hospital_tags = {'amenity': 'hospital'}
    assert classify_poi_category(hospital_tags) == "Hospital"
    
    # Test other/unknown
    other_tags = {'highway': 'primary'}
    assert classify_poi_category(other_tags) == "Other"
    
    # Test empty tags
    assert classify_poi_category({}) == "Other"


def test_assign_categories_to_nodes():
    """Test assigning categories to graph nodes."""
    G = nx.MultiDiGraph()
    G.add_node(1, x=0, y=0, landuse='residential')
    G.add_node(2, x=0.001, y=0.001, amenity='shop')
    G.add_node(3, x=0.002, y=0.002, public_transport='station')
    
    G_with_categories = assign_categories_to_nodes(G)
    
    # Check that categories were assigned
    for node, data in G_with_categories.nodes(data=True):
        assert 'category' in data
        assert data['category'] in ['Residential', 'Business', 'Transport', 'School', 'Hospital', 'Other']


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q", "-s"]))
