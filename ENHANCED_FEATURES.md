# TPSA25 Enhanced Traffic Toolkit Features

This document describes the enhanced features added to the TPSA25 traffic modeling toolkit, including population + demand-aware visualization and SCATS integration.

## 🎯 Overview

The enhanced toolkit provides a complete pipeline for traffic modeling with:
- **Population + Census Integration**: Real census data with spatial joins
- **SCATS Data Processing**: Multi-year traffic data aggregation
- **Enhanced Visualization**: Time-of-day scaling, choropleth layers, interactive maps
- **Supernode Caching**: Efficient computation with persistent storage
- **CLI Integration**: Easy-to-use command-line interface

## 🏘️ Population + Census Integration

### Features
- **JSON-stat Census Data**: Parse official CSO census files with `pyjstat`
- **Spatial Joins**: Assign population to nodes using GeoJSON boundaries
- **POI Fallback**: Use OpenStreetMap POI data when census unavailable
- **Heuristic Assignment**: Category-based capacity estimation
- **Demand Profiles**: Time-of-day demand patterns per category

### Usage
```python
from traffic_model.population import assign_population_capacity_enhanced

# With census data
G = assign_population_capacity_enhanced(G, "data/raw/census/population_small_area_2022.px")

# Automatic fallback to POI/heuristic
G = assign_population_capacity_enhanced(G)
```

### Data Requirements
- `data/raw/census/population_small_area_2022.px` - CSO census data (PC-Axis format)
- `data/raw/census/small_area_boundaries_2022.geojson` - Area boundaries

## 📊 SCATS Data Integration

### Features
- **Multi-year Processing**: Unpack and merge all SCATS archives
- **Standardized Columns**: Consistent data format across years
- **Demand Profiles**: Average hourly patterns per site
- **Metadata Extraction**: Year/month from filenames
- **Error Handling**: Graceful handling of corrupted files

### Usage
```python
from datahub.scats import process_all_scats_data, load_scats_profiles

# Process all SCATS data
demand_profiles = process_all_scats_data("data/raw/scats", "data/processed")

# Load demand profiles
profiles = load_scats_profiles("data/processed/scats_demand_profiles.csv")
```

### CLI Commands
```bash
# Process all SCATS archives
python -m datahub.cli scats-process

# View demand profiles
python -m datahub.cli scats-profiles
```

## 🗺️ Enhanced Visualization

### Features
- **Time-of-Day Scaling**: Marker sizes adjust based on demand profiles
- **Category Colors**: Consistent color scheme (Residential=blue, Business=red, etc.)
- **Choropleth Layers**: Population density visualization
- **Enhanced Popups**: Full node information (capacity, demand, category)
- **Interactive Legends**: Toggleable layers with category mapping
- **Saturation Coloring**: Roads colored by traffic load/capacity ratio

### Usage
```python
from traffic_model.viz import save_enhanced_folium_map

# Create map with time-of-day scaling
save_enhanced_folium_map(
    G, 
    "output.html",
    layers="all",
    time_of_day="evening",
    census_data_path="data/raw/census/small_area_boundaries_2022.geojson"
)
```

### Map Features
- **Supernodes**: Sized by `log(population_capacity)` × `demand_factor`
- **Roads**: Colored by saturation (green → orange → red)
- **Choropleth**: Population density from census boundaries
- **Popups**: Node ID, category, capacity, demand profile
- **Layers**: Toggleable roads, supernodes, junctions, categories, choropleth

## 🚀 Supernode Caching

### Features
- **Persistent Storage**: Save supernodes to JSON files
- **Automatic Loading**: Reuse cached supernodes on subsequent runs
- **Force Recomputation**: `--force-supernodes` flag for fresh computation
- **Place-specific**: Separate cache files per location
- **Metadata Preservation**: Include geometry, category, population capacity

### Usage
```python
from traffic_model.super_nodes import detect_and_cache_supernodes

# With caching (default)
supernodes = detect_and_cache_supernodes(G, "Dublin, Ireland")

# Force recomputation
supernodes = detect_and_cache_supernodes(G, "Dublin, Ireland", force_recompute=True)
```

### Cache Files
- `data/processed/supernodes_dublin_ireland.json`
- `data/processed/supernodes_cork_ireland.json`
- etc.

## 🖥️ CLI Integration

### Enhanced Map Command
```bash
# Basic enhanced map
traffic-model map --place "Dublin, Ireland" --with-population --out dublin.html

# Evening traffic with population scaling
traffic-model map --place "Dublin, Ireland" --with-population --time-of-day evening --out dublin_evening.html

# Force recompute supernodes
traffic-model map --place "Dublin, Ireland" --with-population --force-supernodes --out dublin_fresh.html

# With census data for choropleth
traffic-model map --place "Dublin, Ireland" --with-population --census-path data/raw/census/population_small_area_2022.px --out dublin_with_choropleth.html
```

### SCATS Processing Commands
```bash
# Process all SCATS archives
python -m datahub.cli scats-process

# View demand profiles
python -m datahub.cli scats-profiles

# List available SCATS resources
python -m datahub.cli scats-list
```

## 🧪 Testing

### Test Coverage
- **Population Tests**: Census integration, POI estimation, demand profiles
- **SCATS Tests**: ZIP processing, aggregation, demand profiles
- **Visualization Tests**: Time-of-day scaling, marker sizing, popup content
- **Supernode Tests**: Caching, loading, force recomputation

### Running Tests
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test suites
python -m pytest tests/test_population.py -v
python -m pytest tests/test_scats.py -v
python -m pytest tests/test_viz.py -v
python -m pytest tests/test_supernodes.py -v
```

## 📁 File Structure

```
data/
├── raw/
│   ├── census/
│   │   ├── population_small_area_2022.px
│   │   └── small_area_boundaries_2022.geojson
│   └── scats/
│       ├── 2020/
│       ├── 2021/
│       ├── 2022/
│       ├── 2023/
│       └── 2024/
└── processed/
    ├── supernodes_dublin_ireland.json
    ├── scats_combined_data.csv
    ├── scats_demand_profiles.csv
    └── dublin_*.html
```

## 🎯 Example Workflow

### Complete Pipeline
```bash
# 1. Process SCATS data (optional)
python -m datahub.cli scats-process

# 2. Create enhanced traffic map
traffic-model map --place "Dublin, Ireland" \
    --with-population \
    --time-of-day morning \
    --out data/processed/dublin_morning.html

# 3. View the interactive map
# Open data/processed/dublin_morning.html in a web browser
```

### Python API
```python
from traffic_model import graph_build
from traffic_model.population import assign_population_capacity_enhanced
from traffic_model.super_nodes import detect_and_cache_supernodes, collapse_supernodes
from traffic_model.viz import save_enhanced_folium_map

# Build graph
G = graph_build.build_graph("Dublin, Ireland")

# Add population capacity
G = assign_population_capacity_enhanced(G)

# Create supernodes
supernodes = detect_and_cache_supernodes(G, "Dublin, Ireland")
G = collapse_supernodes(G, supernodes)

# Generate map
save_enhanced_folium_map(G, "dublin.html", time_of_day="evening")
```

## 🔧 Dependencies

### Required
- `networkx` - Graph processing
- `pandas` - Data manipulation
- `folium` - Interactive maps
- `numpy` - Numerical operations

### Optional (for enhanced features)
- `pyjstat` - JSON-stat census data parsing
- `geopandas` - Spatial data processing
- `shapely` - Geometric operations

### Installation
```bash
pip install networkx pandas folium numpy
pip install pyjstat geopandas shapely  # For enhanced features
```

## 🎉 Results

The enhanced toolkit produces interactive Folium maps with:

✅ **Supernodes** scaled by population capacity (adjusted for time-of-day demand)  
✅ **Roads** colored by saturation (green → orange → red)  
✅ **Popups** showing category, capacity, demand profile  
✅ **Layer control** with toggleable overlays (roads, categories, choropleth)  
✅ **Legend** for category colors  
✅ **Cached supernode** computation for faster subsequent runs  
✅ **SCATS demand profiles** for realistic traffic patterns  
✅ **Census integration** for accurate population data  

This provides a complete, production-ready traffic modeling and visualization system for urban planning and transportation analysis.
