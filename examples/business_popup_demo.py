#!/usr/bin/env python3
"""
Business Popup Demo

This script demonstrates the enhanced business popup functionality that shows:
- Business name (from brand, name, operator, shop, amenity, office)
- Business type (shop, amenity, office, landuse, google_place_type)
- Person capacity (population capacity for business nodes)

Usage:
    python examples/business_popup_demo.py
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from traffic_model.viz import _supernode_popup_html


def demo_business_popups():
    """Demonstrate different types of business popups."""
    print("🏢 Business Popup Demo")
    print("=" * 50)
    
    # Example 1: Restaurant with brand name
    print("\n1. Restaurant with Brand Name:")
    print("-" * 30)
    restaurant_data = {
        "category": "Business",
        "brand": "McDonald's",
        "amenity": "fast_food",
        "population_capacity": 60,
        "demand_profile": {"morning": 0.8, "day": 1.0, "evening": 0.7, "night": 0.2}
    }
    popup = _supernode_popup_html(101, restaurant_data)
    print("Business Name: McDonald's")
    print("Business Type: fast_food")
    print("Person Capacity: 60")
    
    # Example 2: Shop with name
    print("\n2. Shop with Name:")
    print("-" * 30)
    shop_data = {
        "category": "Business",
        "name": "Tesco Express",
        "shop": "supermarket",
        "population_capacity": 150,
        "demand_profile": {"morning": 1.0, "day": 0.8, "evening": 0.3, "night": 0.1}
    }
    popup = _supernode_popup_html(102, shop_data)
    print("Business Name: Tesco Express")
    print("Business Type: supermarket")
    print("Person Capacity: 150")
    
    # Example 3: Office building
    print("\n3. Office Building:")
    print("-" * 30)
    office_data = {
        "category": "Business",
        "name": "Tech Solutions Ltd",
        "office": "company",
        "population_capacity": 200,
        "demand_profile": {"morning": 1.0, "day": 0.9, "evening": 0.1, "night": 0.0}
    }
    popup = _supernode_popup_html(103, office_data)
    print("Business Name: Tech Solutions Ltd")
    print("Business Type: company")
    print("Person Capacity: 200")
    
    # Example 4: Google Places shopping mall
    print("\n4. Google Places Shopping Mall:")
    print("-" * 30)
    mall_data = {
        "category": "Business",
        "name": "Dublin Shopping Centre",
        "google_place_type": "shopping_mall",
        "population_capacity": 1000,
        "demand_profile": {"morning": 0.3, "day": 0.8, "evening": 0.9, "night": 0.1}
    }
    popup = _supernode_popup_html(104, mall_data)
    print("Business Name: Dublin Shopping Centre")
    print("Business Type: shopping_mall")
    print("Person Capacity: 1000")
    
    # Example 5: Non-business node (for comparison)
    print("\n5. Non-Business Node (for comparison):")
    print("-" * 30)
    residential_data = {
        "category": "Residential",
        "landuse": "residential",
        "population_capacity": 100,
        "demand_profile": {"morning": 0.2, "day": 0.3, "evening": 0.8, "night": 1.0}
    }
    popup = _supernode_popup_html(105, residential_data)
    print("Category: Residential")
    print("Population Capacity: 100")
    print("(No business-specific information shown)")
    
    print("\n✅ Business popup demo completed!")
    print("\nWhen you click on business nodes in the map, you'll see:")
    print("- Business Name: The actual name of the business")
    print("- Business Type: The type of business (shop, amenity, office, etc.)")
    print("- Person Capacity: The estimated capacity (employees + visitors)")
    print("\nThis information comes from:")
    print("- OSM POI data (shop, amenity, office tags)")
    print("- Google Places API (name, place_type)")
    print("- Enhanced category detection")


if __name__ == "__main__":
    demo_business_popups()
