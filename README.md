# TPSA25 Traffic Modelling, Simulation, and Data Ingestion

A cohesive toolkit for city-scale traffic modelling and simulation used in the TPSA25 Hackathon. It brings together three components:

- traffic_model: Build, analyse, and visualise road graphs (OSMnx/NetworkX) and flows; export Folium maps.
- traffic_sim: Lightweight capacity-aware, probabilistic traffic simulator on graphs (synthetic or OSM-derived).
- datahub: Data ingestion utilities for Smart Dublin SCATS and TII traffic counts.

Highlights
- Graph build from OpenStreetMap with OSMnx
- Neighbourhood detection and collapse into supernodes
- Synthetic or real flow attachment and Folium map export
- Probabilistic flow simulation with capacity constraints
- Smart Dublin (SCATS) and TII data utilities

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

Repository structure

- src/traffic_model/: Road graph loading, neighbourhood detection, simplification, flows, viz, CLI
- src/traffic_sim/: Simulation (capacity, demand, routing, simulate loop, viz, CLI)
- src/datahub/: Data ingestion (SCATS via CKAN/HTML, TII), CLI
- configs/: Demo and example configuration files
- tests/: Unit and smoke tests
- data/: Local data storage (ignored by Git); use data/raw, data/processed
- WARP.md: Terminal usage guide and recent fixes

Data sources and attribution

- OpenStreetMap via OSMnx – adhere to OSM and OSMnx attribution
- Smart Dublin SCATS datasets – respect portal terms and robots.txt
- TII traffic counts – manual exports recommended; the portal layout may change

Notes and gotchas

- If SCATS scraping fails due to portal changes, pass a direct resource URL to loaders
- Large graphs can be slow to simplify; consider testing with a smaller place or subset
- Windows users: prefer PowerShell and ensure execution policy allows venv activation

Changelog (recent)

- Added datahub CLI (scats-list, scats-get, tii-list, tii-load)
- Fixed SCATS link discovery and ranking; improved tests
- Resolved duplicate key issue when adding edges to MultiDiGraph
- Added console scripts in packaging for all three CLIs

License

MIT
