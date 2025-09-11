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


def _parse_json_stat_to_dataframe(dimensions: dict, values: list) -> pd.DataFrame:
    """
    Parse JSON-stat dimensions and values into a pandas DataFrame.
    
    Args:
        dimensions: JSON-stat dimensions dictionary
        values: JSON-stat values list
        
    Returns:
        DataFrame with parsed census data
    """
    import itertools
    
    # Extract dimension information
    dim_names = []
    dim_labels = []
    dim_categories = []
    
    for dim_name, dim_info in dimensions.items():
        dim_names.append(dim_name)
        dim_labels.append(dim_info.get('label', dim_name))
        
        # Extract category indices and labels
        category_info = dim_info.get('category', {})
        indices = category_info.get('index', [])
        labels = category_info.get('label', {})
        
        # Create category mapping
        categories = []
        for idx in indices:
            if idx in labels:
                categories.append(labels[idx])
            else:
                categories.append(idx)
        
        dim_categories.append(categories)
    
    # Create all combinations of dimension values
    combinations = list(itertools.product(*dim_categories))
    
    # Create DataFrame
    data = []
    for i, combo in enumerate(combinations):
        if i < len(values):
            row = {}
            for j, (dim_name, dim_label, value) in enumerate(zip(dim_names, dim_labels, combo)):
                row[dim_label] = value
            row['value'] = values[i] if values[i] is not None else 0
            data.append(row)
    
    df = pd.DataFrame(data)
    
    # Standardize column names for common census dimensions
    column_mapping = {
        'Census Year': 'CensusYear',
        'CSO Small Areas 2022': 'Small Area',  # Map the actual column name
        'Small Area': 'Small Area',
        'Sex': 'Sex',
        'Statistic': 'Statistic',
        'Population': 'Population'
    }
    
    for old_name, new_name in column_mapping.items():
        if old_name in df.columns:
            df = df.rename(columns={old_name: new_name})
    
    return df


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


def _get_dublin_filtered_paths(census_path: Path, boundaries_geojson_path: Path) -> tuple[Path, Path]:
    """Get paths for Dublin-only filtered files, creating them if they don't exist."""
    # Create Dublin-only file paths
    census_dir = census_path.parent
    boundaries_dir = boundaries_geojson_path.parent
    
    dublin_census_path = census_dir / f"dublin_18km_{census_path.name}"
    dublin_boundaries_path = boundaries_dir / f"dublin_18km_{boundaries_geojson_path.name}"
    
    return dublin_census_path, dublin_boundaries_path


def _create_dublin_filtered_files(census_path: Path, boundaries_geojson_path: Path) -> tuple[Path, Path]:
    """Create Dublin-only filtered versions of census and boundary files."""
    print("Creating Dublin filtered files (18km radius)...")
    
    dublin_census_path, dublin_boundaries_path = _get_dublin_filtered_paths(census_path, boundaries_geojson_path)
    
    try:
        import geopandas as gpd
        
        # Load full boundaries and filter to Dublin
        print(f"Loading full boundaries from: {boundaries_geojson_path}")
        gdf_boundaries = gpd.read_file(str(boundaries_geojson_path))
        
        # Filter to Dublin area within 18km radius from city center
        original_count = len(gdf_boundaries)
        dublin_areas = None
        
        # Dublin city center coordinates (Spire of Dublin)
        dublin_center_lat = 53.3498
        dublin_center_lon = -6.2603
        
        # 18km radius in degrees (approximate conversion)
        # 1 degree latitude ≈ 111km, 1 degree longitude ≈ 111km * cos(latitude)
        radius_km = 18
        lat_radius = radius_km / 111.0
        lon_radius = radius_km / (111.0 * np.cos(np.radians(dublin_center_lat)))
        
        print(f"Filtering to areas within {radius_km}km of Dublin city center")
        print(f"Dublin center: ({dublin_center_lat}, {dublin_center_lon})")
        
        # Get centroids and filter by 18km radius
        centroids = gdf_boundaries.geometry.centroid
        
        # Calculate distance from Dublin center
        distances = np.sqrt(
            (centroids.y - dublin_center_lat)**2 + 
            (centroids.x - dublin_center_lon)**2
        ) * 111.0  # Convert to km
        
        # Filter areas within 18km radius
        dublin_mask = distances <= radius_km
        dublin_areas = gdf_boundaries[dublin_mask]
        
        if dublin_areas is not None and len(dublin_areas) > 0:
            print(f"Filtered to {len(dublin_areas)} Dublin areas (18km radius) from {original_count} total areas")
            
            # Save Dublin-only boundaries
            dublin_areas.to_file(str(dublin_boundaries_path), driver='GeoJSON')
            print(f"Saved Dublin boundaries (18km radius) to: {dublin_boundaries_path}")
            
            # Get Dublin area identifiers for census filtering
            area_id_cols = ["SA_PUB2022", "SA_PUB2016", "SA_PUB2011", "Small Area", "small_area", "SA", "sa", "GUID", "guid"]
            area_id_col = None
            for col in area_id_cols:
                if col in dublin_areas.columns:
                    area_id_col = col
                    break
            
            if area_id_col is not None:
                dublin_area_ids = set(dublin_areas[area_id_col].dropna().unique())
                print(f"Found {len(dublin_area_ids)} unique Dublin area identifiers")
                
                # Filter census data to Dublin areas only
                if census_path.suffix.lower() == '.px':
                    # For .px files, we need to filter the parsed data
                    df_census = parse_px_file(census_path)
                    if df_census is not None:
                        # Filter to Dublin areas
                        if "SA_PUB2022" in df_census.columns:
                            dublin_census = df_census[df_census["SA_PUB2022"].isin(dublin_area_ids)]
                            print(f"Filtered census data to {len(dublin_census)} Dublin areas")
                            
                            # Save as .px format (we'll save as CSV for simplicity)
                            dublin_census.to_csv(dublin_census_path.with_suffix('.csv'), index=False)
                            print(f"Saved Dublin census data to: {dublin_census_path.with_suffix('.csv')}")
                        else:
                            print("Warning: Could not find SA_PUB2022 column in census data")
                else:
                    # For other formats, copy the file (filtering will happen during loading)
                    import shutil
                    shutil.copy2(census_path, dublin_census_path)
                    print(f"Copied census file to: {dublin_census_path}")
            else:
                print("Warning: Could not find area identifier column, copying original files")
                import shutil
                shutil.copy2(census_path, dublin_census_path)
                shutil.copy2(boundaries_geojson_path, dublin_boundaries_path)
        else:
            print(f"Warning: No Dublin areas found, copying original files")
            import shutil
            shutil.copy2(census_path, dublin_census_path)
            shutil.copy2(boundaries_geojson_path, dublin_boundaries_path)
            
    except Exception as e:
        print(f"Error creating Dublin filtered files: {e}")
        # Fallback: copy original files
        import shutil
        shutil.copy2(census_path, dublin_census_path)
        shutil.copy2(boundaries_geojson_path, dublin_boundaries_path)
    
    return dublin_census_path, dublin_boundaries_path


def load_census_data(census_path: Path, boundaries_geojson_path: Path) -> Optional[pd.DataFrame]:
    """Load and merge census population data with small area boundaries."""
    try:
        # Check if file exists and is readable
        if not census_path.exists():
            warnings.warn(f"Census data file not found: {census_path}")
            return None
        
        # Check for Dublin-only filtered files first
        dublin_census_path, dublin_boundaries_path = _get_dublin_filtered_paths(census_path, boundaries_geojson_path)
        
        # Use Dublin-only files if they exist and force_reprocess is False, otherwise create them
        if not force_reprocess and dublin_census_path.exists() and dublin_boundaries_path.exists():
            print(f"Using cached Dublin files (18km radius):")
            print(f"  Census: {dublin_census_path}")
            print(f"  Boundaries: {dublin_boundaries_path}")
            census_path = dublin_census_path
            boundaries_geojson_path = dublin_boundaries_path
        else:
            if force_reprocess:
                print("Force reprocessing: recreating Dublin filtered files...")
            else:
                print("Dublin filtered files not found, creating them...")
            census_path, boundaries_geojson_path = _create_dublin_filtered_files(census_path, boundaries_geojson_path)
        
        # Try different file formats
        if census_path.suffix.lower() in ['.px', '.csv']:
            # Parse PC-Axis format or CSV
            if census_path.suffix.lower() == '.px' and census_path.exists():
                print(f"Loading PC-Axis data from: {census_path}")
                df_census = parse_px_file(census_path)
            elif census_path.suffix.lower() == '.csv' and census_path.exists():
                print(f"Loading CSV data from: {census_path}")
                df_census = pd.read_csv(census_path)
            else:
                # Try alternative file extensions
                csv_path = census_path.with_suffix('.csv')
                px_path = census_path.with_suffix('.px')
                if csv_path.exists():
                    print(f"Loading CSV data from: {csv_path}")
                    df_census = pd.read_csv(csv_path)
                elif px_path.exists():
                    print(f"Loading PC-Axis data from: {px_path}")
                    df_census = parse_px_file(px_path)
                else:
                    print(f"Error: Neither {census_path} nor alternative formats found")
                    return None
            if df_census is None:
                return None
        else:
            # Parse JSON-stat format manually
            try:
                import json
                
                # Load census JSON-stat data
                print(f"Loading JSON-stat data from: {census_path}")
                with open(census_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Extract dimensions and values
                dimensions = data.get('dimension', {})
                values = data.get('value', [])
                
                # Create a simple parser for this specific JSON-stat structure
                df_census = _parse_json_stat_to_dataframe(dimensions, values)
                print(f"Successfully loaded census data with {len(df_census)} rows and columns: {list(df_census.columns)}")
                    
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
        if census_path.suffix.lower() in ['.px', '.csv']:
            # For .px and .csv files, data is already in the right format
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
        
        # Load boundaries GeoJSON (already filtered to Dublin)
        try:
            import geopandas as gpd
            gdf_boundaries = gpd.read_file(str(boundaries_geojson_path))
            print(f"Loaded {len(gdf_boundaries)} Dublin boundary areas")
            
            # Merge population with boundaries
            # Try different possible column names for the area identifier
            if census_path.suffix.lower() in ['.px', '.csv']:
                # For .px and .csv files, use SA_PUB2022 column
                area_id_cols = ["SA_PUB2022", "SA_PUB2016", "SA_PUB2011", "Small Area", "small_area", "SA", "sa", "GUID", "guid"]
                pop_area_col = "SA_PUB2022"
            else:
                # For JSON-stat files, use GUID column for matching
                area_id_cols = ["SA_GUID_2022", "SA_GUID_2016", "Small Area", "small_area", "SA", "sa", "GUID", "guid"]
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
            
            # Fill missing population with 0 and mark missing data
            merged["population"] = merged["population"].fillna(0)
            merged["has_census_data"] = merged["population"] > 0
            
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
        
        # Assign population to nodes and track statistics
        nodes_with_population = 0
        nodes_without_population = 0
        polygons_without_values = 0
        
        # Check for polygons without population values
        for _, row in census_data.iterrows():
            population = row.get("population", 0)
            if pd.isna(population) or population == 0:
                polygons_without_values += 1
        
        if polygons_without_values > 0:
            print(f"Warning: {polygons_without_values} polygons have no population values")
        
        # Assign population to nodes - ONLY for sources and supernodes
        for _, row in joined.iterrows():
            node_id = row["node_id"]
            population = row.get("population", 0)
            node_data = G.nodes[node_id]
            
            # Check if this is a business sink - if so, preserve its tier-based capacity
            if node_data.get('is_business_sink', False):
                # Business sinks keep their tier-based capacity estimates
                continue
            
            # Only assign population to sources and supernodes
            if pd.notna(population) and population > 0:
                # Check if this is a source or supernode
                category = row.get("category", "Other")
                is_supernode = node_data.get('is_supernode', False)
                
                if category == 'Residential' or is_supernode:
                    G.nodes[node_id]["population_capacity"] = int(population)
                    G.nodes[node_id]["demand_profile"] = assign_demand_profile(category)
                    nodes_with_population += 1
                else:
                    nodes_without_population += 1
            else:
                nodes_without_population += 1
        
        print(f"Population assignment: {nodes_with_population} nodes with population, {nodes_without_population} nodes without")
        
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
        
        # Get the area identifier column name
        area_id_col = None
        for col in ['SA_PUB2022', 'SA_PUB2016', 'SA_PUB2011', 'Small Area', 'small_area', 'SA', 'sa', 'GUID', 'guid']:
            if col in census_data.columns:
                area_id_col = col
                break
        
        if area_id_col is None:
            print("Warning: Could not find area identifier column for synthetic source creation")
            return G
        
        districts_with_sources = districts_with_sources.groupby(area_id_col).size()
        
        # Find districts with population but no sources
        districts_needing_sources = []
        
        # Filter districts that need sources
        districts_to_process = census_data[
            (census_data['population'] > 0) & 
            (~census_data[area_id_col].isin(districts_with_sources.index))
        ].copy()
        
        if len(districts_to_process) > 0:
            print(f"Processing {len(districts_to_process)} districts for synthetic source creation")
            
            # Use robust centroid calculation for all districts at once
            try:
                # Project to Irish Grid (EPSG:2157) for better centroid calculation
                districts_projected = districts_to_process.to_crs('EPSG:2157')
                centroids_projected = districts_projected.geometry.centroid
                # Project back to WGS84
                centroids_wgs84 = centroids_projected.to_crs('EPSG:4326')
                
                # Create the districts_needing_sources list
                for idx, row in districts_to_process.iterrows():
                    district_id = row.get(area_id_col, f'district_{idx}')
                    population = row.get('population', 0)
                    
                    districts_needing_sources.append({
                        'district_id': district_id,
                        'population': population,
                        'geometry': centroids_wgs84.loc[idx]
                    })
                    
            except Exception as e:
                print(f"Warning: Could not calculate projected centroids, using simple centroids: {e}")
                # Fallback to original geometry centroids
                for idx, row in districts_to_process.iterrows():
                    district_id = row.get(area_id_col, f'district_{idx}')
                    population = row.get('population', 0)
                    
                    districts_needing_sources.append({
                        'district_id': district_id,
                        'population': population,
                        'geometry': row.geometry.centroid
                    })
        
        print(f"Creating {len(districts_needing_sources)} synthetic source nodes for districts without sources")
        print(f"Total districts with population: {len(census_data[census_data['population'] > 0])}")
        print(f"Districts with existing sources: {len(districts_with_sources)}")
        print(f"Districts needing sources: {len(districts_to_process)}")
        
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
                # Convert distance to meters (rough approximation)
                length_meters = min_distance * 111000
                
                G.add_edge(
                    synthetic_node_id, 
                    nearest_junction,
                    length=length_meters,
                    highway='residential',
                    synthetic_edge=True,  # Use the specified tag name
                    synthetic_connection=True  # Keep for backward compatibility
                )
                G.add_edge(
                    nearest_junction, 
                    synthetic_node_id,
                    length=length_meters,
                    highway='residential',
                    synthetic_edge=True,  # Use the specified tag name
                    synthetic_connection=True  # Keep for backward compatibility
                )
        
        return G
        
    except Exception as e:
        print(f"Error creating synthetic sources: {e}")
        return G


def assign_population_capacity_enhanced(G: nx.Graph, census_path: Optional[Union[str, Path]] = None, force_reprocess: bool = False) -> nx.Graph:
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
    # BUT preserve business sink tier-based capacities
    for node, data in G.nodes(data=True):
        # Skip business sinks - they already have tier-based capacity estimates
        if data.get('is_business_sink', False):
            continue
            
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