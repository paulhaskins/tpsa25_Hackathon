"""
test_sinks_offices.py - Smoke tests for office sink detection functionality.
"""

import networkx as nx
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from src.traffic_model.places import (
    query_google_places_offices, 
    map_offices_to_sink_nodes, 
    create_sink_nodes_from_offices,
    detect_office_sinks,
    _is_office_place,
    _extract_office_info,
    _estimate_office_capacity
)


def test_office_place_detection():
    """Test office place detection logic."""
    # Test positive cases
    assert _is_office_place(['establishment', 'point_of_interest'], 'office building')
    assert _is_office_place(['premise'], 'corporate headquarters')
    assert _is_office_place(['finance'], 'business center')
    assert _is_office_place(['point_of_interest'], 'test ltd')
    assert _is_office_place(['establishment'], 'consulting services')
    
    # Test negative cases
    assert not _is_office_place(['restaurant'], 'pizza place')
    assert not _is_office_place(['hospital'], 'medical center')
    assert not _is_office_place(['school'], 'elementary school')
    assert not _is_office_place(['gas_station'], 'fuel station')
    assert not _is_office_place(['shopping_mall'], 'retail center')
    
    print("✓ Office place detection tests passed!")


def test_office_info_extraction():
    """Test office information extraction from Google Places data."""
    mock_place_data = {
        'name': 'Test Office Building',
        'geometry': {'location': {'lat': 53.3498, 'lng': -6.2603}},
        'rating': 4.2,
        'user_ratings_total': 45,
        'business_status': 'OPERATIONAL',
        'types': ['establishment', 'point_of_interest'],
        'formatted_address': '123 Test Street, Dublin',
        'vicinity': 'Dublin City Center'
    }
    
    office_info = _extract_office_info(mock_place_data)
    
    assert office_info['name'] == 'Test Office Building'
    assert office_info['lat'] == 53.3498
    assert office_info['lon'] == -6.2603
    assert office_info['rating'] == 4.2
    assert office_info['user_ratings_total'] == 45
    assert office_info['place_type'] == 'office'
    assert office_info['types'] == ['establishment', 'point_of_interest']
    
    print("✓ Office info extraction tests passed!")


def test_office_capacity_estimation():
    """Test office capacity estimation logic."""
    # Test base capacity
    base_office = {'rating': 0, 'user_ratings_total': 0, 'name': 'test'}
    capacity = _estimate_office_capacity(base_office)
    assert capacity == 50  # Base capacity
    
    # Test high rating multiplier
    high_rating_office = {'rating': 4.8, 'user_ratings_total': 0, 'name': 'test'}
    capacity = _estimate_office_capacity(high_rating_office)
    assert capacity > 50  # Should be higher due to rating
    
    # Test high review count multiplier
    high_reviews_office = {'rating': 0, 'user_ratings_total': 150, 'name': 'test'}
    capacity = _estimate_office_capacity(high_reviews_office)
    assert capacity > 50  # Should be higher due to review count
    
    # Test headquarters multiplier
    hq_office = {'rating': 0, 'user_ratings_total': 0, 'name': 'corporate headquarters'}
    capacity = _estimate_office_capacity(hq_office)
    assert capacity > 50  # Should be higher due to name
    
    # Test capacity bounds
    assert 10 <= capacity <= 1000  # Should be within bounds
    
    print("✓ Office capacity estimation tests passed!")


def test_office_mapping_to_nodes():
    """Test mapping office locations to graph nodes."""
    # Create test graph
    G = nx.Graph()
    G.add_node(1, x=-6.2603, y=53.3498)  # Dublin city center
    G.add_node(2, x=-6.2503, y=53.3598)  # Nearby node
    G.add_node(3, x=-6.2703, y=53.3398)  # Another nearby node
    
    # Create test office data
    offices_df = pd.DataFrame([
        {
            'name': 'Test Office 1',
            'lat': 53.3498,
            'lon': -6.2603,
            'rating': 4.0,
            'user_ratings_total': 50,
            'place_type': 'office'
        },
        {
            'name': 'Test Office 2',
            'lat': 53.3598,
            'lon': -6.2503,
            'rating': 3.5,
            'user_ratings_total': 25,
            'place_type': 'office'
        }
    ])
    
    # Map offices to nodes
    sink_mappings = map_offices_to_sink_nodes(offices_df, G, max_distance=1000)
    
    # Should map to nodes 1 and 2
    assert len(sink_mappings) == 2
    assert 1 in sink_mappings
    assert 2 in sink_mappings
    
    # Check sink node properties
    sink_1 = sink_mappings[1]
    assert sink_1['type'] == 'sink'
    assert sink_1['place_type'] == 'office'
    assert sink_1['office_name'] == 'Test Office 1'
    assert sink_1['person_capacity'] > 0
    assert 'office_lat' in sink_1
    assert 'office_lon' in sink_1
    
    print("✓ Office mapping to nodes tests passed!")


def test_sink_node_creation():
    """Test creating sink nodes from office data."""
    # Create test graph
    G = nx.Graph()
    G.add_node(1, x=-6.2603, y=53.3498, category='Other')
    G.add_node(2, x=-6.2503, y=53.3598, category='Other')
    
    # Create test office data
    offices_df = pd.DataFrame([
        {
            'name': 'Test Office',
            'lat': 53.3498,
            'lon': -6.2603,
            'rating': 4.0,
            'user_ratings_total': 50,
            'place_type': 'office'
        }
    ])
    
    # Create sink nodes
    G_with_sinks = create_sink_nodes_from_offices(G, offices_df)
    
    # Check that node 1 is now a sink
    assert G_with_sinks.nodes[1]['is_sink'] == True
    assert G_with_sinks.nodes[1]['category'] == 'Business'
    assert G_with_sinks.nodes[1]['type'] == 'sink'
    assert G_with_sinks.nodes[1]['office_name'] == 'Test Office'
    assert G_with_sinks.nodes[1]['person_capacity'] > 0
    
    print("✓ Sink node creation tests passed!")


@patch('src.traffic_model.places.query_google_places_offices')
def test_office_sink_detection_integration(mock_query_offices):
    """Test the complete office sink detection integration."""
    # Mock the Google Places API response
    mock_offices_df = pd.DataFrame([
        {
            'name': 'Mock Office',
            'lat': 53.3498,
            'lon': -6.2603,
            'rating': 4.0,
            'user_ratings_total': 50,
            'place_type': 'office'
        }
    ])
    mock_query_offices.return_value = mock_offices_df
    
    # Create test graph
    G = nx.Graph()
    G.add_node(1, x=-6.2603, y=53.3498, category='Other')
    
    # Run office sink detection
    G_with_sinks = detect_office_sinks(G, "Dublin, Ireland")
    
    # Verify the mock was called
    mock_query_offices.assert_called_once_with("Dublin, Ireland", None)
    
    # Check that sink was created
    assert G_with_sinks.nodes[1]['is_sink'] == True
    assert G_with_sinks.nodes[1]['category'] == 'Business'
    
    print("✓ Office sink detection integration tests passed!")


@patch('src.traffic_model.places.query_google_places_offices')
def test_office_sink_detection_no_api_key(mock_query_offices):
    """Test office sink detection when no API key is available."""
    # Mock empty response (no API key)
    mock_query_offices.return_value = pd.DataFrame()
    
    # Create test graph
    G = nx.Graph()
    G.add_node(1, x=-6.2603, y=53.3498, category='Other')
    
    # Run office sink detection
    G_with_sinks = detect_office_sinks(G, "Dublin, Ireland")
    
    # Graph should be unchanged
    assert G_with_sinks.nodes[1]['category'] == 'Other'
    assert 'is_sink' not in G_with_sinks.nodes[1]
    
    print("✓ Office sink detection no API key tests passed!")


def test_sink_node_rendering():
    """Test that sink nodes render with correct colors and popups."""
    from src.traffic_model.viz import _sink_popup_html, COLORS
    
    # Create sink node data
    sink_data = {
        'name': 'Test Office Building',
        'place_type': 'office',
        'population_capacity': 250,
        'sink_attraction_morning': 1.0,
        'sink_attraction_day': 0.8,
        'sink_attraction_evening': 0.2,
        'sink_attraction_night': 0.0
    }
    
    # Test popup generation
    popup_html = _sink_popup_html(1, sink_data)
    
    assert 'Test Office Building' in popup_html
    assert 'Sink (Office)' in popup_html
    assert 'Person Capacity: 250' in popup_html
    assert 'Demand Weights:' in popup_html
    assert '<table' not in popup_html  # No raw tables
    
    # Test color consistency
    assert COLORS['sink'] == '#EF4444'  # Red color for sinks
    
    print("✓ Sink node rendering tests passed!")


if __name__ == "__main__":
    test_office_place_detection()
    test_office_info_extraction()
    test_office_capacity_estimation()
    test_office_mapping_to_nodes()
    test_sink_node_creation()
    test_office_sink_detection_integration()
    test_office_sink_detection_no_api_key()
    test_sink_node_rendering()
    print("All sink detection tests completed successfully!")
