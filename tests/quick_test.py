from traffic_model import (
  load_graph_from_csv, generate_synthetic_flows,
  detect_and_collapse, save_folium_flow_map,
  read_scats_zip,
  estimate_sources_sinks_and_flows,
)
from pathlib import Path
import os


def print_header(title: str):
  print("\n" + "="*20 + f" {title} " + "="*20)


def _find_local_scats_zip(root: Path) -> Path | None:
  """Search recursively for a local SCATS ZIP under root and return the first match.

  We support different portal packaging; just pick any .zip that looks like SCATS.
  """
  candidates: list[Path] = []
  for dirpath, _, filenames in os.walk(root):
    for fn in filenames:
      if fn.lower().endswith('.zip') and 'scats' in fn.lower():
        candidates.append(Path(dirpath) / fn)
  # Prefer newer names by modification time
  candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
  return candidates[0] if candidates else None


def main():
  print_header("Load local SCATS ZIP (no network)")
  df = None
  for folder in [Path('data/raw'), Path('data/raw/scats'), Path('data')]:
    z = _find_local_scats_zip(folder)
    if z is None:
      continue
    print("Using local SCATS zip:", z)
    try:
      df = read_scats_zip(z)
      print("SCATS shape:", df.shape)
      print("SCATS head:\n", df.head())
      break
    except Exception as e:
      print("Failed to read", z, e)
      df = None

  print_header("Load graph from CSV with capacities")
  try:
    G = load_graph_from_csv("data/node_data.csv", "data/edges_data.csv", edges_out_csv="data/edges_with_capacity.csv")
    print("Nodes:", G.number_of_nodes(), "Edges:", G.number_of_edges())
    cap_samples = []
    for _, _, _, d in G.edges(keys=True, data=True):
      if "capacity" in d:
        cap_samples.append(d["capacity"])
      if len(cap_samples) >= 5:
        break
    print("Sample capacities:", cap_samples)

    print_header("Generate synthetic flows and simplify")
    generate_synthetic_flows(G)
    Gc, neighborhoods = detect_and_collapse(G)
    print(f"Collapsed neighborhoods: {len(neighborhoods)}")
    supernodes = [n for n, d in Gc.nodes(data=True) if d.get("is_supernode")]
    print("Supernodes:", supernodes[:5])

    print_header("Estimate sources, sinks, and expected flows (if local data available)")
    # Try to locate optional inputs; pass None if not found
    def first_existing(paths):
      for p in paths:
        if Path(p).exists():
          return str(p)
      return None
    census_path = first_existing([
      "data/census.geojson", "data/census.shp", "data/census/census.shp",
    ])
    landuse_path = first_existing([
      "data/landuse.geojson", "data/landuse.shp", "data/landuse/landuse.shp",
    ])
    pois_jobs_path = first_existing([
      "data/pois.geojson", "data/pois.shp", "data/pois/pois.shp", "data/jobs.geojson", "data/jobs.shp",
    ])

    try:
      results = estimate_sources_sinks_and_flows(
        Gc,
        census_path=census_path,
        landuse_path=landuse_path,
        pois_jobs_path=pois_jobs_path,
        scats_df=df,
      )
      sn_stats = results.get("supernode_stats")
      if sn_stats is not None and not sn_stats.empty:
        print("Supernode stats columns:", list(sn_stats.columns)[:8])
        print(sn_stats.head())
    except Exception as e:
      print("Source/sink/flow estimation skipped:", e)

    print_header("Export Folium map (with SCATS if available)")
    out = Path("flow_map.html")
    # Pass scats_df to enable supernode stats if mapping is possible; otherwise N/A tooltips
    save_folium_flow_map(Gc, out, scats_df=df)
    print("Wrote:", out.resolve())
  except FileNotFoundError as e:
    print("Graph CSVs not found:", e)


if __name__ == "__main__":
    main()