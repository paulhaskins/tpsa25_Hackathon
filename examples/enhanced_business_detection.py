#!/usr/bin/env python3
"""
Enhanced Business/Sink Detection Example

This script demonstrates the enhanced business and sink detection features:
- OSM POI Integration with OSMnx
- Google Places API integration (optional)
- Fallback heuristics for business detection
- Enhanced population capacity assignment
- Updated visualization with proper color scheme

Usage:
    python examples/enhanced_business_detection.py
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from traffic_model import graph_build
from traffic_model.categories import assign_categories_enhanced
from traffic_model.population import assign_population_capacity_enhanced, get_population_summary
from traffic_model.super_nodes import detect_and_cache_supernodes, collapse_supernodes
from traffic_model.junctions import annotate_junctions
from traffic_model.capacity import attach_capacity_to_graph
from traffic_model.load_graph import generate_synthetic_flows
from traffic_model.viz import save_enhanced_folium_map


def main():
    """Run the enhanced business/sink detection pipeline."""
    print("🏢 Enhanced Business/Sink Detection Pipeline")
    print("=" * 60)
    
    # Configuration
    place = "Dublin, Ireland"
    output_dir = Path("data/processed")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Build the graph
    print(f"📍 Building graph for {place}...")
    G = graph_build.build_graph(place)
    print(f"   Graph has {len(G.nodes)} nodes and {len(G.edges)} edges")
    
    # Step 2: Add capacity annotations
    print("🛣️  Computing road capacities...")
    G = attach_capacity_to_graph(G)
    
    # Step 3: Detect and collapse supernodes (with caching)
    print("🏘️  Detecting and collapsing supernodes...")
    supernodes = detect_and_cache_supernodes(G, place, force_recompute=False)
    G = collapse_supernodes(G, supernodes)
    print(f"   Collapsed to {len(G.nodes)} supernodes")
    
    # Step 4: Enhanced category assignment with POI detection
    print("🏷️  Enhanced category classification with POI detection...")
    print("   This will:")
    print("   - Query OSM POIs (schools, hospitals, shops, offices, etc.)")
    print("   - Optionally query Google Places API (if API key available)")
    print("   - Apply business detection heuristics")
    print("   - Map POIs to nearest road nodes")
    
    G = assign_categories_enhanced(
        G, 
        place, 
        use_osm=True,      # Use OSM POI data
        use_google=True,   # Use Google Places API (if available)
        use_heuristics=True # Use fallback heuristics
    )
    
    # Step 5: Annotate junctions with efficiency
    print("🚦 Computing junction efficiency...")
    G = annotate_junctions(G)
    
    # Step 6: Assign population capacity with enhanced business support
    print("👥 Assigning population capacity...")
    census_path = Path("data/raw/census/population_small_area_2022.px")
    if census_path.exists():
        print("   Using census data for population assignment...")
        G = assign_population_capacity_enhanced(G, census_path)
    else:
        print("   No census data found, using POI-based assignment...")
        G = assign_population_capacity_enhanced(G)
    
    # Print population summary
    summary = get_population_summary(G)
    print(f"   Population capacity summary:")
    print(f"     Total capacity: {summary['total_capacity']:,}")
    print(f"     Average capacity: {summary['average_capacity']:.1f}")
    print(f"     Categories: {list(summary['categories'].keys())}")
    
    # Step 7: Generate synthetic flows for visualization
    print("🌊 Generating synthetic flows...")
    generate_synthetic_flows(G)
    
    # Step 8: Create enhanced maps showing business/sink detection
    print("🗺️  Creating enhanced maps with business/sink detection...")
    
    time_periods = ["morning", "day", "evening", "night"]
    for time_of_day in time_periods:
        output_file = output_dir / f"dublin_business_{time_of_day}.html"
        print(f"   Creating {time_of_day} map: {output_file}")
        
        save_enhanced_folium_map(
            G, 
            output_file, 
            layers="all",
            time_of_day=time_of_day,
            census_data_path=Path("data/raw/census/small_area_boundaries_2022.geojson")
        )
    
    print("\n✅ Enhanced business/sink detection pipeline completed!")
    print(f"📁 Output files saved to: {output_dir}")
    print("\n🌐 Open the HTML files in a web browser to view the interactive maps.")
    print("   Each map now shows:")
    print("   - 🏢 Business nodes (red) - detected from POIs and heuristics")
    print("   - 🏫 School nodes (green) - detected from OSM education POIs")
    print("   - 🏥 Hospital nodes (purple) - detected from OSM medical POIs")
    print("   - 🚌 Transport nodes (orange) - detected from OSM transport POIs")
    print("   - 🏠 Residential nodes (blue) - detected from OSM residential areas")
    print("   - Roads colored by saturation (green → orange → red)")
    print("   - Supernodes sized by population capacity (scaled by time-of-day demand)")
    print("   - Population density choropleth layer")
    print("   - Popups with full info (capacity, demand, category)")
    print("   - Toggleable layers + updated legend")


def demonstrate_poi_detection():
    """Demonstrate POI detection capabilities."""
    print("\n🔍 POI Detection Demonstration")
    print("=" * 40)
    
    from traffic_model.categories import query_osm_pois, classify_poi_category
    
    # Test POI classification
    test_pois = [
        {"amenity": "restaurant"},
        {"shop": "supermarket"},
        {"amenity": "school"},
        {"amenity": "hospital"},
        {"railway": "station"},
        {"landuse": "residential"}
    ]
    
    print("POI Classification Examples:")
    for poi in test_pois:
        category = classify_poi_category(poi)
        print(f"  {poi} → {category}")
    
    # Note: Actual OSM querying would require OSMnx and internet connection
    print("\nNote: OSM POI querying requires OSMnx library and internet connection.")
    print("To enable OSM POI detection, install: pip install osmnx")


def demonstrate_google_places():
    """Demonstrate Google Places API integration."""
    print("\n🌍 Google Places API Integration")
    print("=" * 40)
    
    import os
    
    if os.getenv('GOOGLE_API_KEY'):
        print("✅ Google Places API key found in environment")
        print("   The system will query Google Places for:")
        print("   - Shopping malls")
        print("   - Airports")
        print("   - Train stations")
        print("   - Hospitals")
        print("   - Universities")
        print("   - Government buildings")
        print("   - Banks")
        print("   - Restaurants")
        print("   - Hotels")
        print("   - Tourist attractions")
    else:
        print("⚠️  No Google Places API key found")
        print("   To enable Google Places integration:")
        print("   1. Get a Google Places API key")
        print("   2. Set environment variable: export GOOGLE_API_KEY=your_key")
        print("   3. Install: pip install googlemaps")


if __name__ == "__main__":
    # Demonstrate POI detection
    demonstrate_poi_detection()
    
    # Demonstrate Google Places integration
    demonstrate_google_places()
    
    # Run the main pipeline
    main()
