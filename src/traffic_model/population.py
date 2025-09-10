"""
population.py - Population capacity assignment for traffic modeling.
"""

import networkx as nx
from typing import Dict, Any, Optional, Union, Tuple
from pathlib import Path
import numpy as np
import pandas as pd
import warnings
import json

# Default capacity mappings (enhanced for business/sink detection)
DEFAULT_CAPACITY = {
    "Residential": 100,
    "Business": 500,  # Increased for business areas (employees + visitors)
    "School": 500,
    "Hospital": 300,  # Increased for medical facilities
    "Transport": 2000,
    "Other": 50,
}

# Time-of-day demand profiles
TIME_PROFILE = {
    "Residential": {"morning": 0.2, "day": 0.3, "evening": 0.8, "night": 1.0},
    "Business": {"morning": 1.0, "day": 0.8, "evening": 0.2, "night": 0.0},
    "School": {"morning": 1.0, "day": 0.5, "evening": 0.0, "night": 0.0},
    "Hospital": {"morning": 0.5, "day": 0.5, "evening": 0.5, "night": 0.5},
    "Transport": {"morning": 1.0, "day": 0.6, "evening": 1.0, "night": 0.2},
    "Other": {"morning": 0.3, "day": 0.5, "evening": 0.3, "night": 0.2},
}

# POI-based capacity estimation (enhanced for business/sink detection)
POI_CAPACITY_ESTIMATES = {
    "house": 4,
    "apartment": 2,
    "residential": 50,
    "office": 50,  # Increased for office buildings
    "shop": 20,  # Increased for retail
    "restaurant": 50,  # Increased for restaurants
    "cafe": 30,  # Increased for cafes
    "bank": 25,  # Increased for banks
    "bus_station": 1000,
    "train_station": 2000,
    "airport": 5000,
    "ferry_terminal": 500,
    "school": 500,
    "university": 2000,
    "college": 1000,
    "kindergarten": 100,
    "hospital": 300,  # Increased for hospitals
    "clinic": 100,  # Increased for clinics
    "pharmacy": 20,  # Increased for pharmacies
    "shopping_mall": 2000,  # New: shopping malls
    "government": 200,  # New: government buildings
    "hotel": 100,  # New: hotels
    "museum": 150,  # New: museums
    "police": 50,  # New: police stations
    "fire_station": 30,  # New: fire stations
}


def estimate_poi_capacity(node_data: Dict[str, Any]) -> int:
    """Estimate population capacity based on POI attributes."""
    capacity = 0
    
    for key, value in node_data.items():
        if key in ['amenity', 'shop', 'office', 'leisure', 'tourism']:
            if isinstance(value, str):
                value_lower = value.lower()
                for poi_type, poi_capacity in POI_CAPACITY_ESTIMATES.items():
                    if poi_type in value_lower:
                        capacity += poi_capacity
    
    if 'building' in node_data:
        building = str(node_data['building']).lower()
        if 'house' in building or 'residential' in building:
            capacity += POI_CAPACITY_ESTIMATES['house']
        elif 'apartment' in building:
            capacity += POI_CAPACITY_ESTIMATES['apartment']
        elif 'office' in building:
            capacity += POI_CAPACITY_ESTIMATES['office']
    
    if 'landuse' in node_data:
        landuse = str(node_data['landuse']).lower()
        if 'residential' in landuse:
            capacity += POI_CAPACITY_ESTIMATES['residential']
        elif 'commercial' in landuse or 'retail' in landuse:
            capacity += POI_CAPACITY_ESTIMATES['shop']
    
    return max(capacity, 1)


def assign_heuristic_capacity(category: str) -> int:
    """Assign capacity based on node category using heuristics."""
    return DEFAULT_CAPACITY.get(category, DEFAULT_CAPACITY["Other"])


def assign_demand_profile(category: str) -> Dict[str, float]:
    """Assign time-of-day demand profile based on category."""
    return TIME_PROFILE.get(category, TIME_PROFILE["Other"]).copy()


def assign_population_capacity(G: nx.Graph, census_path: Optional[Union[str, Path]] = None) -> nx.Graph:
    """Assign population/demand capacity to nodes."""
    G = G.copy()
    
    for node, data in G.nodes(data=True):
        population_capacity = 0
        demand_profile = {}
        
        # Method 1: Try POI-based estimation
        try:
            population_capacity = estimate_poi_capacity(data)
        except Exception as e:
            warnings.warn(f"Failed to estimate POI capacity for node {node}: {e}")
        
        # Method 2: Heuristic fallback
        if population_capacity == 0:
            category = data.get('category', 'Other')
            population_capacity = assign_heuristic_capacity(category)
        
        # Assign demand profile based on category
        category = data.get('category', 'Other')
        demand_profile = assign_demand_profile(category)
        
        # Store in node attributes
        G.nodes[node]['population_capacity'] = population_capacity
        G.nodes[node]['demand_profile'] = demand_profile
    
    return G


def parse_px_file(px_path: Path) -> Optional[pd.DataFrame]:
    """Parse PC-Axis (.px) file format to extract population data."""
    try:
        with open(px_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract small area codes from VALUES section
        sa_codes = []
        if 'VALUES("CSO Small Areas 2022")=' in content:
            start = content.find('VALUES("CSO Small Areas 2022")=') + len('VALUES("CSO Small Areas 2022")=')
            end = content.find('VALUES("Age")=', start)
            if end == -1:
                end = content.find('VALUES("Sex")=', start)
            if end == -1:
                end = content.find('DATA=', start)
            
            values_section = content[start:end].strip()
            # Remove quotes and split by comma
            values_section = values_section.replace('"', '').replace('\n', '').replace(' ', '')
            sa_codes = [code.strip() for code in values_section.split(',') if code.strip()]
        
        # Extract data values
        data_values = []
        if 'DATA=' in content:
            data_start = content.find('DATA=') + 5
            data_section = content[data_start:].strip()
            # Split by whitespace and convert to integers
            data_values = [int(val) for val in data_section.split() if val.isdigit()]
        
        # The data is likely structured as: [area1_age1_sex1, area1_age1_sex2, area1_age2_sex1, ...]
        # We need to aggregate by area to get total population per area
        if len(sa_codes) != len(data_values):
            print(f"Info: Data has {len(sa_codes)} areas and {len(data_values)} data points")
            print("Aggregating data by area (summing across age/sex dimensions)...")
            
            # Calculate how many data points per area
            data_per_area = len(data_values) // len(sa_codes)
            print(f"Data points per area: {data_per_area}")
            
            # Aggregate data by area
            aggregated_values = []
            for i in range(len(sa_codes)):
                start_idx = i * data_per_area
                end_idx = start_idx + data_per_area
                area_total = sum(data_values[start_idx:end_idx])
                aggregated_values.append(area_total)
            
            data_values = aggregated_values
        
        # Create DataFrame
        df = pd.DataFrame({
            'SA_PUB2022': sa_codes,
            'Population': data_values
        })
        
        print(f"Successfully parsed .px file with {len(df)} small areas")
        return df
        
    except Exception as e:
        print(f"Error parsing .px file: {e}")
        return None


def load_census_data(census_path: Path, boundaries_geojson_path: Path) -> Optional[pd.DataFrame]:
    """Load and merge census population data with small area boundaries."""
    try:
        # Check if file exists and is readable
        if not census_path.exists():
            warnings.warn(f"Census data file not found: {census_path}")
            return None
        
        # Try different file formats
        if census_path.suffix.lower() == '.px':
            # Parse PC-Axis format
            print(f"Loading PC-Axis data from: {census_path}")
            df_census = parse_px_file(census_path)
            if df_census is None:
                return None
        else:
            # Try to import pyjstat for JSON-stat parsing
            try:
                from pyjstat import pyjstat
                
                # Load census JSON-stat data
                print(f"Loading JSON-stat data from: {census_path}")
                dataset = pyjstat.Dataset.read(str(census_path))
                df_census = dataset.write('dataframe')
                print(f"Successfully loaded census data with {len(df_census)} rows and columns: {list(df_census.columns)}")
                    
            except ImportError:
                print("Info: pyjstat not available, using dummy census data for demonstration")
                df_census = pd.DataFrame({
                    'Small Area': ['Dummy_Area_1', 'Dummy_Area_2'],
                    'value': [1000, 1500],
                    'Sex': ['Both sexes', 'Both sexes'],
                    'Statistic': ['Population', 'Population']
                })
            except Exception as e:
                print(f"Error parsing JSON-stat file: {e}")
                print("Info: Using dummy census data for demonstration")
                df_census = pd.DataFrame({
                    'Small Area': ['Dummy_Area_1', 'Dummy_Area_2'],
                    'value': [1000, 1500],
                    'Sex': ['Both sexes', 'Both sexes'],
                    'Statistic': ['Population', 'Population']
                })
        
        # Handle different data formats
        if census_path.suffix.lower() == '.px':
            # For .px files, data is already in the right format
            population_by_area = df_census.rename(columns={"Population": "population"})
        else:
            # For JSON-stat files, filter and group
            if "Sex" in df_census.columns:
                df_census = df_census[df_census["Sex"] == "Both sexes"]
            if "Statistic" in df_census.columns:
                df_census = df_census[df_census["Statistic"].str.contains("Population", case=False, na=False)]
            
            # Group by Small Area
            population_by_area = df_census.groupby("Small Area")["value"].sum().reset_index()
            population_by_area = population_by_area.rename(columns={"value": "population"})
        
        # Load boundaries GeoJSON
        try:
            import geopandas as gpd
            gdf_boundaries = gpd.read_file(str(boundaries_geojson_path))
            
            # Filter to County Dublin only
            if 'COUNTY_ENGLISH' in gdf_boundaries.columns:
                dublin_areas = gdf_boundaries[gdf_boundaries['COUNTY_ENGLISH'].str.contains('Dublin', case=False, na=False)]
                print(f"Filtered to {len(dublin_areas)} Dublin areas from {len(gdf_boundaries)} total areas")
                gdf_boundaries = dublin_areas
            elif 'COUNTY_GAEILGE' in gdf_boundaries.columns:
                dublin_areas = gdf_boundaries[gdf_boundaries['COUNTY_GAEILGE'].str.contains('Baile Átha Cliath', case=False, na=False)]
                print(f"Filtered to {len(dublin_areas)} Dublin areas from {len(gdf_boundaries)} total areas")
                gdf_boundaries = dublin_areas
            else:
                print("Warning: No county column found, using all areas")
            
            # Merge population with boundaries
            # Try different possible column names for the area identifier
            if census_path.suffix.lower() == '.px':
                # For .px files, use SA_PUB2022 column
                area_id_cols = ["SA_PUB2022", "SA_PUB2016", "SA_PUB2011", "Small Area", "small_area", "SA", "sa", "GUID", "guid"]
                pop_area_col = "SA_PUB2022"
            else:
                # For JSON-stat files, use Small Area column
                area_id_cols = ["Small Area", "small_area", "SA", "sa", "GUID", "guid"]
                pop_area_col = "Small Area"
            
            area_id_col = None
            for col in area_id_cols:
                if col in gdf_boundaries.columns:
                    area_id_col = col
                    break
            
            if area_id_col is None:
                print("Info: Could not find area identifier column in boundaries GeoJSON, using dummy data")
                return None
            
            # Merge on area identifier - use copy to avoid fragmentation warnings
            merged = gdf_boundaries.copy()
            merged = merged.merge(
                population_by_area, 
                left_on=area_id_col, 
                right_on=pop_area_col, 
                how="left"
            )
            
            # Fill missing population with 0
            merged["population"] = merged["population"].fillna(0)
            
            return merged
            
        except ImportError:
            warnings.warn("geopandas not available, cannot load boundaries")
            return None
            
    except Exception as e:
        warnings.warn(f"Error loading census data: {e}")
        return None


def assign_population_from_census(G: nx.Graph, census_data: pd.DataFrame) -> nx.Graph:
    """Assign population to nodes based on spatial join with census boundaries."""
    G = G.copy()
    
    try:
        import geopandas as gpd
        from shapely.geometry import Point
        
        # Create GeoDataFrame from graph nodes
        nodes_data = []
        for node, data in G.nodes(data=True):
            if data.get("x") is not None and data.get("y") is not None:
                nodes_data.append({
                    "node_id": node,
                    "geometry": Point(data["x"], data["y"]),
                    "category": data.get("category", "Other")
                })
        
        if not nodes_data:
            warnings.warn("No nodes with coordinates found for spatial join")
            return G
        
        # Create GeoDataFrame with copy to avoid fragmentation warnings
        gdf_nodes = gpd.GeoDataFrame(nodes_data.copy(), geometry="geometry")
        gdf_nodes.crs = "EPSG:4326"  # Assume WGS84
        
        # Ensure census data has proper CRS
        if census_data.crs is None:
            census_data.crs = "EPSG:4326"
        
        # Perform spatial join
        joined = gdf_nodes.sjoin(census_data, how="left", predicate="within")
        
        # Assign population to nodes
        for _, row in joined.iterrows():
            node_id = row["node_id"]
            population = row.get("population", 0)
            
            if pd.notna(population) and population > 0:
                G.nodes[node_id]["population_capacity"] = int(population)
                # Assign demand profile based on category
                category = row.get("category", "Other")
                G.nodes[node_id]["demand_profile"] = assign_demand_profile(category)
        
        # Create synthetic source nodes for districts with population but no sources
        G = create_synthetic_sources_for_districts(G, census_data)
        
        return G
        
    except ImportError:
        warnings.warn("geopandas not available for spatial join")
        return G


def create_synthetic_sources_for_districts(G: nx.MultiDiGraph, census_data) -> nx.MultiDiGraph:
    """Create synthetic source nodes for districts with population but no existing sources."""
    try:
        import geopandas as gpd
        from shapely.geometry import Point
        
        # Get all existing nodes with their coordinates
        existing_nodes = []
        for node, data in G.nodes(data=True):
            if 'x' in data and 'y' in data:
                existing_nodes.append({
                    'node_id': node,
                    'geometry': Point(data['x'], data['y']),
                    'has_population': 'population_capacity' in data and data['population_capacity'] > 0
                })
        
        if not existing_nodes:
            return G
        
        # Create GeoDataFrame of existing nodes
        existing_gdf = gpd.GeoDataFrame(existing_nodes, geometry='geometry', crs=census_data.crs)
        
        # Find districts with population but no sources
        districts_with_sources = existing_gdf.sjoin(census_data, how='inner', predicate='within')
        districts_with_sources = districts_with_sources.groupby('SA_PUB2022').size()
        
        # Find districts with population but no sources
        districts_needing_sources = []
        for idx, row in census_data.iterrows():
            district_id = row.get('SA_PUB2022', f'district_{idx}')
            population = row.get('population', 0)
            
            if population > 0 and district_id not in districts_with_sources:
                districts_needing_sources.append({
                    'district_id': district_id,
                    'population': population,
                    'geometry': row.geometry.centroid  # Use centroid as source location
                })
        
        print(f"Creating {len(districts_needing_sources)} synthetic source nodes for districts without sources")
        
        # Create synthetic source nodes
        # Handle both string and integer node IDs
        max_node_id = 0
        for node in G.nodes():
            try:
                node_id = int(node) if isinstance(node, str) and node.isdigit() else node
                if isinstance(node_id, int) and node_id > max_node_id:
                    max_node_id = node_id
            except (ValueError, TypeError):
                continue
        
        synthetic_node_id = max_node_id + 1
        for district in districts_needing_sources:
            # Create synthetic source node
            synthetic_node_id += 1
            G.add_node(
                synthetic_node_id,
                x=district['geometry'].x,
                y=district['geometry'].y,
                lat=district['geometry'].y,
                lon=district['geometry'].x,
                population_capacity=int(district['population']),
                category='Residential',
                is_synthetic_source=True,
                district_id=district['district_id']
            )
            
            # Find nearest junction to connect to
            nearest_junction = None
            min_distance = float('inf')
            
            for node, data in G.nodes(data=True):
                if 'x' in data and 'y' in data and not data.get('is_synthetic_source', False):
                    # Calculate distance
                    dx = data['x'] - district['geometry'].x
                    dy = data['y'] - district['geometry'].y
                    distance = (dx*dx + dy*dy)**0.5
                    
                    if distance < min_distance:
                        min_distance = distance
                        nearest_junction = node
            
            # Connect synthetic source to nearest junction
            if nearest_junction is not None:
                G.add_edge(
                    synthetic_node_id, 
                    nearest_junction,
                    length=min_distance * 111000,  # Rough conversion to meters
                    highway='residential',
                    synthetic_connection=True
                )
                G.add_edge(
                    nearest_junction, 
                    synthetic_node_id,
                    length=min_distance * 111000,
                    highway='residential',
                    synthetic_connection=True
                )
        
        return G
        
    except Exception as e:
        print(f"Error creating synthetic sources: {e}")
        return G


def assign_population_capacity_enhanced(G: nx.Graph, census_path: Optional[Union[str, Path]] = None) -> nx.Graph:
    """Enhanced population capacity assignment with census integration."""
    G = G.copy()
    
    # Try census data first if available
    if census_path:
        census_path = Path(census_path)
        if census_path.exists():
            # Look for boundaries file in same directory
            boundaries_path = census_path.parent / "small_area_boundaries_2022.geojson"
            if boundaries_path.exists():
                census_data = load_census_data(census_path, boundaries_path)
                if census_data is not None:
                    G = assign_population_from_census(G, census_data)
                    print(f"Assigned population from census data to {sum(1 for n, d in G.nodes(data=True) if 'population_capacity' in d)} nodes")
    
    # Fallback to POI-based and heuristic assignment for remaining nodes
    for node, data in G.nodes(data=True):
        if 'population_capacity' not in data:
            # Method 1: Try POI-based estimation
            try:
                population_capacity = estimate_poi_capacity(data)
            except Exception as e:
                warnings.warn(f"Failed to estimate POI capacity for node {node}: {e}")
                population_capacity = 0
            
            # Method 2: Heuristic fallback
            if population_capacity == 0:
                category = data.get('category', 'Other')
                population_capacity = assign_heuristic_capacity(category)
            
            # Assign demand profile based on category
            category = data.get('category', 'Other')
            demand_profile = assign_demand_profile(category)
            
            # Store in node attributes
            G.nodes[node]['population_capacity'] = population_capacity
            G.nodes[node]['demand_profile'] = demand_profile
    
    return G


def get_population_summary(G: nx.Graph) -> Dict[str, Any]:
    """Get summary statistics of population capacity assignment."""
    capacities = []
    categories = []
    
    for node, data in G.nodes(data=True):
        if 'population_capacity' in data:
            capacities.append(data['population_capacity'])
            categories.append(data.get('category', 'Other'))
    
    if not capacities:
        return {"total_capacity": 0, "average_capacity": 0, "categories": {}}
    
    summary = {
        "total_capacity": sum(capacities),
        "average_capacity": np.mean(capacities),
        "median_capacity": np.median(capacities),
        "min_capacity": min(capacities),
        "max_capacity": max(capacities),
        "categories": {}
    }
    
    # Category breakdown
    for category in set(categories):
        cat_capacities = [cap for cap, cat in zip(capacities, categories) if cat == category]
        summary["categories"][category] = {
            "count": len(cat_capacities),
            "total": sum(cat_capacities),
            "average": np.mean(cat_capacities)
        }
    
    return summary


__all__ = [
    "assign_population_capacity",
    "assign_population_capacity_enhanced",
    "get_population_summary",
    "load_census_data",
    "assign_population_from_census",
    "DEFAULT_CAPACITY",
    "TIME_PROFILE",
    "POI_CAPACITY_ESTIMATES",
]