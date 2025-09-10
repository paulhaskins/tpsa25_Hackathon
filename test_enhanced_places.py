#!/usr/bin/env python3
"""
Test script for enhanced Google Places API integration.
"""

import os
from pathlib import Path
from src.traffic_model.places import search_places, query_google_places_offices

def test_enhanced_places():
    """Test the enhanced Google Places integration."""
    
    # Check if API key is available
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        print("❌ GOOGLE_API_KEY environment variable not set")
        print("   Set it with: export GOOGLE_API_KEY='your_api_key_here'")
        return
    
    print("✅ Google Places API key found")
    
    # Test location
    place = "Dublin, Ireland"
    
    print(f"\n🔍 Testing enhanced Google Places search for: {place}")
    print("=" * 60)
    
    # Test individual search queries
    test_queries = [
        "office building Dublin",
        "business park Dublin", 
        "tech company Dublin",
        "government office Dublin",
        "hospital Dublin",
        "university Dublin"
    ]
    
    print("\n📋 Testing individual search queries:")
    for query in test_queries:
        print(f"\n  🔎 Searching: {query}")
        results = search_places(query, place, radius=10000, api_key=api_key)  # 10km radius for testing
        print(f"     Found {len(results)} results")
        
        if results:
            # Show first result as example
            first_result = results[0]
            print(f"     Example: {first_result.get('name', 'Unknown')} - {first_result.get('types', [])}")
    
    print("\n" + "=" * 60)
    print("🏢 Testing comprehensive office detection:")
    
    # Test the main function
    offices_df = query_google_places_offices(place, api_key)
    
    if not offices_df.empty:
        print(f"✅ Found {len(offices_df)} business sink locations")
        
        # Show breakdown by type
        if 'place_type' in offices_df.columns:
            type_counts = offices_df['place_type'].value_counts()
            print("\n📊 Breakdown by type:")
            for place_type, count in type_counts.items():
                print(f"   {place_type}: {count}")
        
        # Show some examples
        print("\n📍 Example locations:")
        for i, (_, row) in enumerate(offices_df.head(5).iterrows()):
            name = row.get('name', 'Unknown')
            place_type = row.get('place_type', 'office')
            rating = row.get('rating', 0)
            print(f"   {i+1}. {name} ({place_type}) - Rating: {rating}")
    else:
        print("❌ No business sink locations found")
    
    print("\n💾 Cache files created in: data/raw/places/")
    cache_dir = Path("data/raw/places")
    if cache_dir.exists():
        cache_files = list(cache_dir.glob("*.json"))
        print(f"   {len(cache_files)} cache files found")
        for cache_file in cache_files[:5]:  # Show first 5
            print(f"   - {cache_file.name}")
        if len(cache_files) > 5:
            print(f"   ... and {len(cache_files) - 5} more")

if __name__ == "__main__":
    test_enhanced_places()
