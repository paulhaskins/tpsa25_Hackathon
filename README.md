# TPSA25 Traffic Modelling, Simulation, and Data Ingestion

A cohesive toolkit for city-scale traffic modelling and simulation used in the TPSA25 Hackathon. It brings together three components:

- traffic_model: Build, analyse, and visualise road graphs (OSMnx/NetworkX) and flows; export Folium maps.
- traffic_sim: Lightweight capacity-aware, probabilistic traffic simulator on graphs (synthetic or OSM-derived).
- datahub: Data ingestion utilities for Smart Dublin SCATS and TII traffic counts.

## Program Capabilities

### 🗺️ **Graph Building & Network Analysis**
- **OpenStreetMap Integration**: Build comprehensive road networks for any city using OSMnx
- **Network Simplification**: Automatically detect and collapse neighborhoods into supernodes for efficient simulation
- **Multi-format Support**: Load graphs from GraphML, CSV, or build directly from OSM data
- **Capacity Estimation**: Compute realistic road capacities based on lanes, speed limits, and road types
- **Connectivity Analysis**: Analyze network structure and identify critical nodes/edges

### 🚗 **Traffic Simulation & Modeling**
- **Probabilistic Flow Simulation**: Realistic traffic flow with capacity constraints and congestion modeling
- **Time-step Evolution**: Multi-step simulation with configurable time intervals and parameters
- **Demand Modeling**: Generate realistic traffic patterns with peak/off-peak variations
- **Route Optimization**: Shortest-path routing with congestion-aware transition probabilities
- **Synthetic Networks**: Create test networks for simulation experiments and validation

### 📊 **Data Integration & Processing**
- **Real-time Data Access**: Automated SCATS (Smart Dublin) and TII traffic data integration
- **Data Discovery**: Intelligent resource discovery and ranking from CKAN portals
- **Format Standardization**: Convert between various traffic data formats and standards
- **Caching System**: Efficient local caching to minimize redundant downloads
- **Data Quality**: Built-in data cleaning, validation, and normalization

### 🎯 **Population & Flow Estimation**
- **Gravity Modeling**: Estimate traffic flows using population, land use, and POI data
- **Source-Sink Analysis**: Identify traffic sources (residential) and sinks (commercial/employment)
- **Census Integration**: Incorporate population data for realistic flow estimation
- **POI Weighting**: Use points of interest (schools, hospitals, offices) to model attraction
- **Time-based Patterns**: Model different traffic patterns for various time periods

### 📈 **Visualization & Analysis**
- **Interactive Maps**: Generate interactive Folium maps with traffic flow overlays
- **Time-series Visualization**: Animate traffic evolution over time with HTML outputs
- **Saturation Mapping**: Visualize network congestion and capacity utilization
- **Flow Analysis**: Analyze traffic patterns, bottlenecks, and network performance
- **Export Capabilities**: Export results in multiple formats (HTML, CSV, GraphML)

### 🛠️ **Command-Line Tools**
- **traffic-model**: Complete graph building, simplification, and flow attachment pipeline
- **traffic-sim**: Run traffic simulations with configurable parameters
- **datahub**: Access and process SCATS/TII data with automated discovery

### 🔧 **Technical Features**
- **Modular Architecture**: Three independent but integrated packages for different workflows
- **Comprehensive Testing**: 12 passing tests covering all major functionality
- **Flexible Configuration**: YAML-based configuration for different cities and scenarios
- **Error Handling**: Robust error handling with graceful fallbacks
- **Performance Optimized**: Efficient algorithms for large-scale network processing

Installation

- Python >= 3.10 recommended
- Create a virtual environment and install from source

```bash
python -m venv .venv
# Windows PowerShell
. .venv\Scripts\Activate.ps1
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
# Or install the package in editable mode
pip install -e .
```

CLI entry points

After installation, three console scripts are available:

- traffic-model: high-level graph build/simplify/attach-flow operations
- traffic-sim: simulation demos on synthetic or OSM graphs
- datahub: SCATS/TII data helper commands

Examples

traffic_model

Build and simplify a city graph, then attach flows and export:

```bash
traffic-model --help
traffic-model build --place "Dublin, Ireland" --out data/processed/dublin.graphml
traffic-model simplify --in data/processed/dublin.graphml --out data/processed/dublin_simplified.graphml
traffic-model attach-flow --graph data/processed/dublin_simplified.graphml --flows data/sample_flows.csv --out data/processed/dublin_with_flows.graphml
# Generate interactive map with traffic visualization and capacity analysis
traffic-model map --place "Dublin, Ireland" --out data/processed/dublin_layers.html --layers all
```

Alternatively, operate on CSV exports already in the repo:

```bash
python - <<'PY'
from traffic_model.load_graph import load_graph_from_csv
G = load_graph_from_csv("node_data.csv", "edges_data.csv", edges_out_csv="edges_with_capacity.csv")
print(G.number_of_nodes(), G.number_of_edges())
PY
```

traffic_sim

Synthetic demo or OSM-based run:

```bash
traffic-sim demo --config configs/demo.yml
# or
traffic-sim osm --place "Dublin, Ireland" --steps 12 --beta 0.5 --alpha 1.0
```

Outputs HTML maps (map_t00.html, map_t01.html, …) coloured by saturation and marking supernodes.

datahub

Discover SCATS datasets, fetch a month, and inspect TII data:

```bash
# List known SCATS resource links
datahub scats-list

# Fetch February 2024 SCATS and load as a tidy DataFrame
datahub scats-get February 2024 --out data/raw

# List TII portal links (may be empty if portal layout changes)
datahub tii-list

# Load a TII CSV/TSV export (local path or URL)
datahub tii-load path_or_url
```

Development and testing

```bash
# Install dev dependencies (if not using requirements.txt)
pip install -e .

# Run tests
pytest -q
# or
pytest tests/ -v
```

## Repository Structure & Capabilities

### Core Packages (`src/`)

#### `src/traffic_model/` - Graph Building & Analysis Engine
**Primary Capabilities:**
- **Graph Construction**: Build road networks from OpenStreetMap using OSMnx
- **Neighborhood Detection**: Identify and collapse single-connection neighborhoods into supernodes
- **Graph Simplification**: Reduce complex road networks while preserving connectivity
- **Flow Integration**: Attach synthetic or real traffic flow data to graph edges
- **Population Modeling**: Gravity-based flow estimation using census, land use, and POI data
- **Interactive Visualization**: Export interactive Folium maps with flow overlays

**Key Modules:**
- `graph_build.py`: OSMnx integration for building drivable street graphs
- `neighborhood.py`: Detect and collapse neighborhoods into supernodes for simulation
- `simplify.py`: Graph simplification algorithms to reduce complexity
- `flow.py`: Attach traffic flow time-series to graph edges
- `population.py`: Gravity model for estimating sources, sinks, and expected flows
- `viz.py`: Folium map generation with flow visualization
- `load_graph.py`: Load graphs from CSV exports with flexible column mapping
- `data_fetch.py`: SCATS data integration and site-to-node mapping
- `cli.py`: Command-line interface for graph operations

#### `src/traffic_sim/` - Traffic Simulation Engine
**Primary Capabilities:**
- **Probabilistic Flow Simulation**: Capacity-aware traffic flow with realistic routing
- **Synthetic Graph Generation**: Create test networks for simulation experiments
- **Time-Step Simulation**: Multi-step traffic evolution with configurable parameters
- **Demand Modeling**: Realistic traffic demand patterns with time-of-day variations
- **Route Optimization**: Shortest-path routing with congestion-aware transitions
- **Real-time Visualization**: Generate HTML maps showing traffic saturation over time

**Key Modules:**
- `graph_loader.py`: Load OSM graphs or generate synthetic networks
- `capacity.py`: Compute edge capacities based on lanes, speed, and road type
- `demand.py`: Build traffic demand schedules with peak/off-peak patterns
- `route.py`: Precompute sink distances and transition probabilities
- `simulate.py`: Core simulation loop with simultaneous flow updates
- `viz.py`: Generate time-step HTML maps with saturation coloring
- `cli.py`: Command-line interface for simulation runs

#### `src/datahub/` - Data Ingestion & Processing
**Primary Capabilities:**
- **SCATS Integration**: Automated discovery and download of Smart Dublin traffic data
- **TII Data Access**: Transport Infrastructure Ireland traffic count processing
- **CKAN API Client**: Generic CKAN portal integration for data discovery
- **Data Normalization**: Standardize and clean traffic count data
- **Caching System**: Local caching to avoid redundant downloads
- **Format Conversion**: Convert between various traffic data formats

**Key Modules:**
- `ckan_client.py`: Minimal CKAN Action API wrapper for data portals
- `scats.py`: Smart Dublin SCATS data discovery, ranking, and loading
- `tii.py`: TII portal metadata fetching and traffic count processing
- `normalize.py`: Data cleaning, resampling, and standardization utilities
- `cache.py`: URL-based caching system for downloaded data
- `cli.py`: Command-line interface for data operations

### Configuration & Data (`configs/`, `data/`)

#### `configs/` - Configuration Files
- `demo.yml`: Default simulation parameters for Dublin traffic simulation
- `dublin.yml`: Dublin-specific graph building and flow attachment settings
- `data_sources.yml`: Data source configurations and API endpoints

#### `data/` - Data Storage
- `raw/`: Downloaded SCATS and TII data (Git-ignored)
- `processed/`: Processed graphs and flow data
- `node_data.csv`: Graph node coordinates and attributes
- `edges_data.csv`: Graph edge connectivity and properties
- `edges_with_capacity.csv`: Edges with computed capacity values
- `sample_flows.csv`: Sample traffic flow time-series data

### Testing & Documentation (`tests/`, `docs/`)

#### `tests/` - Comprehensive Test Suite
- `quick_test.py`: End-to-end integration test covering all major workflows
- `test_data_fetch.py`: SCATS and TII data loading tests
- `test_flows.py`: Flow attachment and processing tests
- `test_imports.py`: Package import and dependency tests
- `test_load_graph.py`: Graph loading from CSV tests
- `test_neighborhoods.py`: Neighborhood detection and collapse tests
- `test_scats_smoke.py`: SCATS data integration smoke tests
- `test_sim_smoke.py`: Simulation engine smoke tests
- `test_viz.py`: Visualization and map generation tests

#### `docs/` - Documentation
- `latex/main.tex`: LaTeX documentation for academic/research use
- `README.md`: Comprehensive project documentation
- `CONTRIBUTING.md`: Development guidelines and contribution process
- `CHANGELOG.md`: Version history and feature updates
- `WARP.md`: Terminal usage patterns and troubleshooting guide
- `PROJECT_SUMMARY.md`: High-level project overview and quick start

### Additional Files
- `pyproject.toml`: Python packaging configuration with console scripts
- `requirements.txt`: Python dependencies and versions
- `Makefile`: Build automation and common tasks
- `LICENSE`: MIT license for open-source usage

Data sources and attribution

- OpenStreetMap via OSMnx – adhere to OSM and OSMnx attribution
- Smart Dublin SCATS datasets – respect portal terms and robots.txt
- TII traffic counts – manual exports recommended; the portal layout may change

Notes and gotchas

- If SCATS scraping fails due to portal changes, pass a direct resource URL to loaders
- Large graphs can be slow to simplify; consider testing with a smaller place or subset
- Windows users: prefer PowerShell and ensure execution policy allows venv activation

Changelog (recent)

- **NEW**: Added `map` command to traffic-model CLI for interactive visualization
- **FIXED**: Type error in capacity.py when OSM lanes data is a list (2025-01-10)
- Added datahub CLI (scats-list, scats-get, tii-list, tii-load)
- Fixed SCATS link discovery and ranking; improved tests
- Resolved duplicate key issue when adding edges to MultiDiGraph
- Added console scripts in packaging for all three CLIs
- Enhanced error handling in capacity computation with robust type checking

License

MIT
