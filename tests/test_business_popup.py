"""Tests for enhanced business popup functionality."""

import networkx as nx
from src.traffic_model.viz import _supernode_popup_html


def test_business_popup_with_shop_info():
    """Test business popup shows shop information."""
    # Create a business node with shop information
    node_data = {
        "category": "Business",
        "shop": "supermarket",
        "name": "Tesco Express",
        "population_capacity": 150,
        "demand_profile": {"morning": 1.0, "day": 0.8, "evening": 0.2, "night": 0.0}
    }
    
    popup_html = _supernode_popup_html(123, node_data)
    
    # Check that business-specific information is included
    assert "Business Name" in popup_html
    assert "Business Type" in popup_html
    assert "Person Capacity" in popup_html
    assert "Tesco Express" in popup_html
    assert "supermarket" in popup_html
    assert "150" in popup_html


def test_business_popup_with_amenity_info():
    """Test business popup shows amenity information."""
    # Create a business node with amenity information
    node_data = {
        "category": "Business",
        "amenity": "restaurant",
        "name": "The Golden Dragon",
        "population_capacity": 80,
        "demand_profile": {"morning": 0.5, "day": 1.0, "evening": 1.0, "night": 0.3}
    }
    
    popup_html = _supernode_popup_html(456, node_data)
    
    # Check that business-specific information is included
    assert "Business Name" in popup_html
    assert "Business Type" in popup_html
    assert "Person Capacity" in popup_html
    assert "The Golden Dragon" in popup_html
    assert "restaurant" in popup_html
    assert "80" in popup_html


def test_business_popup_with_office_info():
    """Test business popup shows office information."""
    # Create a business node with office information
    node_data = {
        "category": "Business",
        "office": "company",
        "name": "Tech Solutions Ltd",
        "population_capacity": 200,
        "demand_profile": {"morning": 1.0, "day": 0.9, "evening": 0.1, "night": 0.0}
    }
    
    popup_html = _supernode_popup_html(789, node_data)
    
    # Check that business-specific information is included
    assert "Business Name" in popup_html
    assert "Business Type" in popup_html
    assert "Person Capacity" in popup_html
    assert "Tech Solutions Ltd" in popup_html
    assert "company" in popup_html
    assert "200" in popup_html


def test_business_popup_with_google_places_info():
    """Test business popup shows Google Places information."""
    # Create a business node with Google Places information
    node_data = {
        "category": "Business",
        "name": "Dublin Shopping Centre",
        "google_place_type": "shopping_mall",
        "population_capacity": 1000,
        "demand_profile": {"morning": 0.3, "day": 0.8, "evening": 0.9, "night": 0.1}
    }
    
    popup_html = _supernode_popup_html(101, node_data)
    
    # Check that business-specific information is included
    assert "Business Name" in popup_html
    assert "Business Type" in popup_html
    assert "Person Capacity" in popup_html
    assert "Dublin Shopping Centre" in popup_html
    assert "shopping_mall" in popup_html
    assert "1000" in popup_html


def test_business_popup_fallback_names():
    """Test business popup with fallback name detection."""
    # Test with brand information
    node_data = {
        "category": "Business",
        "brand": "McDonald's",
        "amenity": "fast_food",
        "population_capacity": 60,
        "demand_profile": {"morning": 0.8, "day": 1.0, "evening": 0.7, "night": 0.2}
    }
    
    popup_html = _supernode_popup_html(202, node_data)
    
    # Check that brand name is used as business name
    assert "McDonald's" in popup_html
    assert "fast_food" in popup_html


def test_non_business_popup():
    """Test that non-business nodes don't show business-specific information."""
    # Create a residential node
    node_data = {
        "category": "Residential",
        "landuse": "residential",
        "population_capacity": 100,
        "demand_profile": {"morning": 0.2, "day": 0.3, "evening": 0.8, "night": 1.0}
    }
    
    popup_html = _supernode_popup_html(303, node_data)
    
    # Check that business-specific information is NOT included
    assert "Business Name" not in popup_html
    assert "Business Type" not in popup_html
    assert "Person Capacity" not in popup_html
    
    # But regular information should still be there
    assert "Category" in popup_html
    assert "Residential" in popup_html
    assert "Population Capacity" in popup_html


def test_business_popup_without_capacity():
    """Test business popup when capacity is not available."""
    # Create a business node without capacity information
    node_data = {
        "category": "Business",
        "shop": "bakery",
        "name": "Corner Bakery",
        "demand_profile": {"morning": 1.0, "day": 0.6, "evening": 0.3, "night": 0.0}
    }
    
    popup_html = _supernode_popup_html(404, node_data)
    
    # Check that business information is still shown
    assert "Business Name" in popup_html
    assert "Business Type" in popup_html
    assert "Person Capacity" in popup_html
    assert "Corner Bakery" in popup_html
    assert "bakery" in popup_html
    assert "N/A" in popup_html  # For missing capacity


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q", "-s"]))
