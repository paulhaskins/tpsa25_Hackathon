Traffic Modelling for Infrastructure Optimisation

A hackathon project to build a map-overlay traffic model with junction nodes and neighbourhood simplification into supernodes. We store flow time-series at nodes/supernodes, run simple analyses (graph algorithms, sensor placement metrology), and visualise on a map.

Quickstart: Minimal Traffic Simulation Demo

This repo includes a lightweight `traffic_sim` package to simulate capacity-aware probabilistic traffic flows on a graph. It runs on a small synthetic grid (no external data) and can try OpenStreetMap (OSM) for a place.

Install

```bash
pip install -r requirements.txt
```

Run demo (synthetic or OSM fallback)

```bash
python -m traffic_sim.cli demo --config configs/demo.yml
```

If OSM loading fails, it falls back to a synthetic grid. Outputs HTML maps per step are written to `outputs/` (e.g., `map_t00.html`, `map_t01.html`, ...). Open them in a browser to see edges colored by saturation and supernodes.

CLI (optional OSM)

```bash
python -m traffic_sim.cli osm --place "Dublin, Ireland" --steps 12 --beta 0.5 --alpha 1.0
```

Files

- `src/traffic_sim/`: simulation package (graph loader, capacity, demand, routing, simulate loop, viz, CLI)
- `configs/demo.yml`: demo parameters
- `examples/run_demo.sh`: convenience script
- `tests/test_sim_smoke.py`: smoke test

Data Ingestion

- List SCATS resources:

```bash
python -m datahub.cli scats-list --verbose
```

- Fetch a given month (SCATS):

```bash
python -m datahub.cli scats-get --month February --year 2024 --out data/raw
```

- List TII DATEX-II links:

```bash
python -m datahub.cli tii-list
```

- Load a TII Traffic Count export (URL or local path):

```bash
python -m datahub.cli tii-load --export path_or_url
```

Note: Respect robots.txt and attribution for Smart Dublin and TII. Do not scrape aggressively; prefer official APIs.

Data sources and where files are saved

- OpenStreetMap street network (via OSMnx):
  - The helper script `google-drive/getGraphGeom.py` downloads the street graph for a place (default: "Dublin, Ireland"), converts to GeoDataFrames, and exports:
    - `data/node_data.csv` and `data/edges_data.csv`: tabular node and edge data
    - `data/adj_matrix.npy`: adjacency matrix of the downloaded graph
    - `data/dublin_interactive_osmnx.html`: an interactive Folium map for inspection
  - The CLI can also save GraphMLs under `data/processed/`:
    - `data/processed/dublin.graphml` (built graph)
    - `data/processed/dublin_simplified.graphml` (simplified graph)

- Flows (time series at nodes):
  - For examples/tests we currently use `data/sample_flows.csv` (synthetic/sample flows).
  - Real-world flows can be sourced from Smart Dublin SCATS. Utilities in `src/traffic_model/data_fetch.py` discover/download SCATS ZIPs and parse them; mapping to node flows is a next step.

Notes:
- Generated/downloaded data are ignored by Git per `.gitignore`.
- If you need placeholders under version control, add `.gitkeep` to `data/`, `data/raw/`, `data/processed/`.

Quickstart

1) Create and activate a virtual environment

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\\Scripts\\activate
```

2) Install dependencies

```bash
pip install -r requirements.txt
```

3) Try the CLI

```bash
python -m traffic_model.cli --help
python -m traffic_model.cli build --place "Dublin, Ireland" --out data/processed/dublin.graphml
python -m traffic_model.cli simplify --in data/processed/dublin.graphml --out data/processed/dublin_simplified.graphml
python -m traffic_model.cli attach-flow --graph data/processed/dublin_simplified.graphml --flows data/sample_flows.csv --out data/processed/dublin_with_flows.graphml
```

4) Run tests

```bash
pytest -q
```

Structure

- src/traffic_model/: Python package with CLI and modules
- configs/: YAML configs (e.g., Dublin)
- examples/: Example flows and usage
- data/: Raw and processed data (not versioned; placeholders provided)
- notebooks/: Jupyter notebooks for experiments
- docs/latex/: LaTeX notes/report
- tests/: Unit tests and sanity checks
- .github/workflows/: CI for linting and tests

Notes

- Graph building uses OSMnx; simplification groups small neighbourhoods into supernodes.
- Flows are attached as node attributes; sample CSV provided.
- Visualisation via Folium (interactive HTML) and OSMnx (static plots).

How the model works (current state)

1) Build or import a street graph
- Option A (CSVs): Run `python google-drive/getGraphGeom.py` to generate `data/node_data.csv`, `data/edges_data.csv`, `data/adj_matrix.npy`, and an interactive map under `data/`. Reload via `traffic_model.load_graph.load_graph_from_csv`.
- Option B (GraphML): Use the CLI to build and simplify GraphMLs in `data/processed/`.

2) Ensure routing attributes and (optional) capacities
- When loading from CSV, `load_graph_from_csv` ensures travel-time related attributes and can export `data/edges_with_capacity.csv` if capacity estimates are produced.

3) Flows
- For now, flows come from `data/sample_flows.csv` or are synthesized. Real SCATS ingestion is scaffolded in `data_fetch.py`.

4) Neighbourhood detection and simplification
- The model groups tightly-connected local areas into "supernodes". See `neighborhood_detect.py` and `neighborhood.py`.

5) Visualisation
- Export Folium maps for interactive inspection of the graph and flows.

Reproducing data locally

- CSV route:
  - `python google-drive/getGraphGeom.py`
  - Load via:
    ```python
    from traffic_model.load_graph import load_graph_from_csv
    G = load_graph_from_csv("data/node_data.csv", "data/edges_data.csv", edges_out_csv="data/edges_with_capacity.csv")
    ```

- GraphML route (CLI): see Quickstart commands for outputs under `data/processed/`.

How the Propgation of traffic flows
Let supernodes of residential areas be denoted by H_i with a capacity H_i and current population/cars h_i. Do the same with roads : R_i max capacity, r_i current population.  Let some supernodes be working areas denoted by W_i with capacity W_i with current population capacity w_i. The residential areas are sources and the working spaces are sinks. The global movement of cars (represented by how r_i change at each time step) needs to be from sources towards sinks. This movement is decided probabilistically depending with probabilities of movementt between r_i and r_i+1 depending on which leads to a position closer to the sink. The total population of cars needs to be conserved. 

Also about the flow map
Using a census map online of the greater dublin region and city center. We are using sinks that are objects that contain a certain amount of people at certain times, so for examples businesses or parks during weekdays or weekends have a certain capacity and draw higher then other sources throught the day and even day of the week (you can add small logic checking for holidays etc),  in the case of weekends business are deactivated and parks are higher used so on and so forht. The super nodes should be accumlation how many people live in the areas the roads the supernodes averaged, so that we can have flow values for different parts of the day. People leave and start these sinks at like 9 am to 6pm and so forth. All of these figures should probably be learned by some pattern from real world data that again we should try and webscrape from online)

Make the capacity of some roads higher based on their lenghts and colour code them based on the value r_i/R_i. Do the same with sources and sinks. Make the capacity proportional to how popular that place is. This is time variant so at each time step the colours should change.
