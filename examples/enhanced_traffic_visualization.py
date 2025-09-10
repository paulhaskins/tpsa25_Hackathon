#!/usr/bin/env python3
"""
Enhanced Traffic Visualization Example

This script demonstrates the full TPSA25 traffic toolkit with:
- Population + Census Integration
- SCATS Data Processing
- Enhanced Visualization with Time-of-Day Scaling
- Supernode Caching
- Choropleth Layers

Usage:
    python examples/enhanced_traffic_visualization.py
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from traffic_model import graph_build
from traffic_model.population import assign_population_capacity_enhanced, get_population_summary
from traffic_model.super_nodes import detect_and_cache_supernodes, collapse_supernodes
from traffic_model.categories import assign_categories_to_nodes
from traffic_model.junctions import annotate_junctions
from traffic_model.capacity import attach_capacity_to_graph
from traffic_model.load_graph import generate_synthetic_flows
from traffic_model.viz import save_enhanced_folium_map
from datahub.scats import process_all_scats_data


def main():
    """Run the enhanced traffic visualization pipeline."""
    print("🚀 TPSA25 Enhanced Traffic Visualization Pipeline")
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
    
    # Step 4: Assign categories to nodes
    print("🏷️  Classifying nodes by category...")
    G = assign_categories_to_nodes(G)
    
    # Step 5: Annotate junctions with efficiency
    print("🚦 Computing junction efficiency...")
    G = annotate_junctions(G)
    
    # Step 6: Assign population capacity with census integration
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
    
    # Step 8: Create enhanced maps for different times of day
    print("🗺️  Creating enhanced maps...")
    
    time_periods = ["morning", "day", "evening", "night"]
    for time_of_day in time_periods:
        output_file = output_dir / f"dublin_{time_of_day}.html"
        print(f"   Creating {time_of_day} map: {output_file}")
        
        save_enhanced_folium_map(
            G, 
            output_file, 
            layers="all",
            time_of_day=time_of_day,
            census_data_path=Path("data/raw/census/small_area_boundaries_2022.geojson")
        )
    
    print("\n✅ Enhanced traffic visualization pipeline completed!")
    print(f"📁 Output files saved to: {output_dir}")
    print("\n🌐 Open the HTML files in a web browser to view the interactive maps.")
    print("   Each map shows:")
    print("   - Roads colored by saturation (green → orange → red)")
    print("   - Supernodes sized by population capacity (scaled by time-of-day demand)")
    print("   - Population density choropleth layer")
    print("   - Popups with full info (capacity, demand, category)")
    print("   - Toggleable layers + legend")


def process_scats_data():
    """Process SCATS data to create demand profiles."""
    print("\n📊 Processing SCATS data...")
    print("=" * 40)
    
    try:
        scats_dir = Path("data/raw/scats")
        output_dir = Path("data/processed")
        
        if scats_dir.exists() and any(scats_dir.rglob("*.zip")):
            demand_profiles = process_all_scats_data(scats_dir, output_dir)
            print(f"✅ Created demand profiles: {len(demand_profiles)} site-hour combinations")
            print(f"   Unique sites: {demand_profiles['Site'].nunique()}")
            print(f"   Hours covered: {sorted(demand_profiles['hour'].unique())}")
        else:
            print("⚠️  No SCATS data found in data/raw/scats/")
            print("   Skipping SCATS processing...")
            
    except Exception as e:
        print(f"❌ Error processing SCATS data: {e}")
        print("   Continuing without SCATS data...")


if __name__ == "__main__":
    # Process SCATS data first (optional)
    process_scats_data()
    
    # Run the main visualization pipeline
    main()
