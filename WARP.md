# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

This is a traffic modeling system built for the TPSA25 Hackathon that focuses on infrastructure optimization. The project builds map-overlay traffic models with junction nodes and neighborhood simplification into supernodes. It stores flow time-series at nodes/supernodes, runs analyses using graph algorithms, and provides interactive visualizations on maps using Folium and OSMnx.

## Common Commands

### Traffic Model CLI
```bash
# View available commands
python -m traffic_model.cli --help

# Build a street graph from OpenStreetMap
python -m traffic_model.cli build --place "Dublin, Ireland" --out data/processed/dublin.graphml

# Simplify graph by grouping neighborhoods into supernodes
python -m traffic_model.cli simplify --in data/processed/dublin.graphml --out data/processed/dublin_simplified.graphml

# Attach flow time-series data to graph nodes
python -m traffic_model.cli attach-flow --graph data/processed/dublin_simplified.graphml --flows examples/sample_flows.csv --out data/processed/dublin_with_flows.graphml

# Generate interactive map with traffic visualization
python -m traffic_model.cli map --place "Dublin, Ireland" --out data/processed/dublin_map.html --layers all
# Alternative using the console script:
traffic-model map --place "Dublin, Ireland" --out data/processed/dublin_layers.html --layers all
```

### Traffic Simulation CLI
```bash
# View simulation commands
python -m traffic_sim.cli --help

# Run demo simulation with config file
python -m traffic_sim.cli demo --config configs/demo.yml

# Run OSM-based simulation
python -m traffic_sim.cli osm --place "Dublin, Ireland" --steps 12 --beta 0.5 --alpha 1.0
```

### Data Hub CLI  
```bash
# List available SCATS datasets
python -m datahub.cli scats-list

# Download SCATS data for specific month/year
python -m datahub.cli scats-get February 2024 --out data/raw

# List TII portal resources
python -m datahub.cli tii-list

# Load TII traffic count data
python -m datahub.cli tii-load path_or_url
```

### Development and Testing
```bash
# Install package in development mode
pip install -e .

# Run all tests
pytest tests/ -v

# Run individual test files
python tests/test_imports.py
python tests/test_data_fetch.py
python tests/test_flows.py
python tests/test_load_graph.py
python tests/test_neighborhoods.py
python tests/test_viz.py
python tests/test_sim_smoke.py

# Run the comprehensive integration test
python tests/quick_test.py

# Check dependencies are available
python -c "import osmnx, networkx, pandas, folium, typer; print('All dependencies available')"

# Test CLI commands
traffic-model --help
traffic-sim --help
datahub --help
```

### Environment Setup
```bash
# Activate the virtual environment
# On Windows (PowerShell)
venv\Scripts\Activate.ps1
# On Windows (Command Prompt)
venv\Scripts\activate.bat
# On macOS/Linux
source venv/bin/activate

# Install dependencies from requirements.txt
pip install -r requirements.txt

# Deactivate virtual environment when done
deactivate
```

### Package Management
```bash
# Create new virtual environment (if needed)
python -m venv venv

# Install all dependencies from requirements.txt (recommended)
pip install -r requirements.txt

# Install additional development dependencies
pip install pytest

# Update requirements.txt after adding dependencies
pip freeze > requirements.txt
```

## Architecture and Code Structure

### Core Components

**Graph Loading & Processing (`load_graph`, `ensure_travel_time_weights`)**
- Downloads street network data from OpenStreetMap using OSMnx
- Adds speed and travel time attributes to graph edges for routing calculations
- Supports different network types (drive, walk, bike)

**Routing Engine (`compute_route`, `nearest_node_from_latlon`)**
- Converts lat/lon coordinates to graph nodes using spatial indexing
- Implements shortest path algorithms with configurable weights (distance vs time)
- Uses NetworkX's Dijkstra implementation for optimal pathfinding

**Animation System (`animate_route`, `interpolate_route`)**
- Interpolates smooth movement along route segments using geodesic distance calculations
- Creates time-based animation frames with configurable speed and intervals
- Handles coordinate transformations between geographic and screen space

**Visualization Layer (matplotlib integration)**
- Uses OSMnx's built-in plotting functions for base map rendering
- Overlays route paths and animated markers
- Supports export to multiple formats (GIF, MP4) with codec selection

### Key Technical Details

- **Coordinate System**: Uses WGS84 lat/lon coordinates, converts internally for distance calculations
- **Distance Calculations**: Uses `ox.distance.great_circle_vec` for accurate geodesic distances
- **Graph Weights**: Supports both "length" (meters) and "travel_time" (seconds) for routing
- **Animation Interpolation**: Linear interpolation in geographic space with constant velocity targeting
- **Memory Management**: Loads entire graph into memory; suitable for city-scale networks

### Default Configuration
- **Place**: Dublin, Ireland
- **Origin**: Trinity College area (53.3438, -6.2546)
- **Destination**: Phoenix Park area (53.4273, -6.2700)
- **Speed**: 10 m/s animation speed
- **Frame Rate**: 50ms intervals (20 FPS equivalent)

### Dependencies Architecture
- **OSMnx**: Primary interface for OpenStreetMap data and network analysis
- **NetworkX**: Graph data structure and shortest path algorithms
- **Matplotlib**: Visualization and animation framework
- **argparse**: Command-line interface (standard library)
- **math**: Mathematical utilities (standard library)

The codebase follows a functional programming approach with clear separation between data loading, computation, and visualization phases.

## Recent Fixes and Troubleshooting

### Import Issues Fixed
- Fixed missing `get_scats_download_links` and `find_scats_zip_links` imports in `__init__.py`
- Added proper BeautifulSoup import handling with fallback in `data_fetch.py`
- Removed duplicate function definitions in `data_fetch.py`

### Test Issues Fixed
- Fixed regex pattern for SCATS ZIP link detection
- Fixed monkeypatch in test_data_fetch.py to target correct module
- Added missing `raise_for_status` method to fake response objects in tests
- Fixed NetworkX `add_edge` duplicate key argument issue in `load_graph.py`

### Test Status
All unit tests are now passing:
- `test_imports.py` ✅
- `test_data_fetch.py` ✅ (2 tests)
- `test_flows.py` ✅
- `test_load_graph.py` ✅
- `test_neighborhoods.py` ✅
- `test_viz.py` ✅

### Common Issues
- If SCATS data download fails, ensure network connectivity to SmartDublin portal
- Graph CSV files (data/node_data.csv, data/edges_data.csv) must exist for integration tests
- Some integration tests may be slow due to graph processing algorithms

### Recent Fixes (Latest)

#### Capacity Type Error Fix (2025-01-10)
- **Issue**: `TypeError: int() argument must be a string, a bytes-like object or a real number, not 'list'` in `capacity.py`
- **Root Cause**: OSM data sometimes provides `lanes` as a list (e.g., `['2', '4']`) rather than a single value
- **Solution**: Enhanced type handling in `attach_capacity_to_graph()` function:
  - Added list detection and processing (takes maximum value from list)
  - Improved error handling with fallbacks to default values
  - Robust type conversion with multiple safety checks
- **Affected Commands**: `traffic-model map` and any capacity computation operations
- **Status**: ✅ Fixed and tested
