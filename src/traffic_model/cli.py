import typer
from pathlib import Path
from . import graph_build, simplify as simplify_mod, flow as flow_mod
from .load_graph import load_graph_from_csv, generate_synthetic_flows
from .data_fetch import load_sample_flow, read_site_coords_csv, map_sites_to_nodes
from .viz import save_folium_flow_map, save_enhanced_folium_map
from .capacity import attach_capacity_to_graph, save_edges_with_capacity
from .super_nodes import detect_supernodes, collapse_supernodes, detect_and_cache_supernodes
from .categories import assign_categories_to_nodes, assign_categories_enhanced
from .junctions import annotate_junctions
from .population import assign_population_capacity, assign_population_capacity_enhanced, get_population_summary
from .places import detect_office_sinks

app = typer.Typer(help="Traffic modelling CLI")


@app.command()
def build(place: str = typer.Option(..., help="Place name for OSMnx graph"),
          out: Path = typer.Option(..., help="Output path for graphml")):
    """Build a drivable street graph for a place and save to GraphML."""
    G = graph_build.build_graph(place)
    graph_build.save_graphml(G, out)
    typer.echo(f"Saved graph to {out}")


@app.command()
def simplify(_in: Path = typer.Option(..., help="Input GraphML path"),
             out: Path = typer.Option(..., help="Output simplified GraphML path")):
    """Simplify a graph by collapsing neighbourhoods into supernodes (placeholder)."""
    G = graph_build.load_graphml(_in)
    Gs = simplify_mod.simplify_graph(G)
    graph_build.save_graphml(Gs, out)
    typer.echo(f"Saved simplified graph to {out}")


@app.command("attach-flow")
def attach_flow(graph: Path = typer.Option(..., help="GraphML path"),
                flows: Path = typer.Option(..., help="CSV of node flows"),
                out: Path = typer.Option(..., help="Output GraphML with flows")):
    """Attach node flow time-series from CSV to the graph (placeholder)."""
    G = graph_build.load_graphml(graph)
    Gf = flow_mod.attach_flows(G, flows)
    graph_build.save_graphml(Gf, out)
    typer.echo(f"Saved graph with flows to {out}")


def main():
    app()


@app.command("pipeline")
def pipeline(
    nodes_csv: Path = typer.Option(..., help="Node CSV (with id, lat, lon)"),
    edges_csv: Path = typer.Option(..., help="Edge CSV (with u, v, lanes, etc.)"),
    site_coords_csv: Path = typer.Option(..., help="SCATS site coordinates CSV"),
    month: str = typer.Option("January", help="Month name for SCATS (e.g., January)"),
    year: int = typer.Option(2024, help="Year for SCATS"),
    out_html: Path = typer.Option("dublin_interactive_osmnx.html", help="Output Folium HTML path"),
    out_edges_with_capacity: Path = typer.Option(None, help="Optional path to write edges with capacity"),
    use_synthetic_if_missing: bool = typer.Option(True, help="If SCATS fails, generate synthetic edge flows"),
):
    """End-to-end pipeline: load graph, fetch SCATS, map to nodes, project flows, simplify, and render HTML."""
    typer.echo("Loading graph from CSVs...")
    G = load_graph_from_csv(nodes_csv, edges_csv, edges_out_csv=out_edges_with_capacity)

    # Try fetching SCATS (January 2024 by default) and attach node flows
    df = None
    try:
        typer.echo(f"Downloading SCATS for {month} {year}...")
        df_raw = load_sample_flow() if (month == "January" and year == 2024) else None
        if df_raw is None:
            # fallback to generic downloader via download_scats_zip inside load_sample_flow signature
            from .data_fetch import download_scats_zip, read_scats_zip
            zip_path = download_scats_zip(month, year)
            df_raw = read_scats_zip(zip_path)
        df = df_raw
    except Exception as e:
        typer.echo(f"SCATS download/load failed: {e}")

    if df is not None:
        typer.echo("Mapping SCATS sites to nearest nodes...")
        site_map = read_site_coords_csv(site_coords_csv)
        df_nodes = map_sites_to_nodes(df, site_map, G)
        # rename mapped column to node_id for attach helper
        df_nodes = df_nodes.rename(columns={"node_id": "node_id"})
        df_nodes = df_nodes.dropna(subset=["node_id"])  # keep only mapped
        df_nodes["node_id"] = df_nodes["node_id"].astype(int)
        typer.echo("Attaching node flow series and projecting to edges...")
        flow_mod.attach_node_flow_series_from_df(G, df_nodes)
        flow_mod.project_node_flows_to_edges(G, method="average")
    elif use_synthetic_if_missing:
        typer.echo("Generating synthetic edge flows (SCATS unavailable)...")
        generate_synthetic_flows(G)
    else:
        typer.echo("No flows attached. Proceeding without flows.")

    typer.echo("Collapsing neighborhoods into supernodes...")
    Gs = simplify_mod.simplify_graph(G)

    typer.echo(f"Rendering Folium map to {out_html}...")
    save_folium_flow_map(Gs, out_html)
    typer.echo("Done.")


@app.command("download-scats")
def download_scats(
    month: str = typer.Option(..., help="Month name, e.g., January"),
    year: int = typer.Option(..., help="Year, e.g., 2024"),
    dest_dir: Path = typer.Option("data/raw", help="Directory to save the ZIP"),
):
    """Download a SCATS monthly ZIP and print the local path."""
    from .data_fetch import download_scats_zip
    path = download_scats_zip(month, year, dest_dir=dest_dir)
    typer.echo(str(path))


@app.command("attach-scats")
def attach_scats(
    graph_in: Path = typer.Option(..., help="Input GraphML path"),
    site_coords_csv: Path = typer.Option(..., help="SCATS site coordinates CSV"),
    out_graph: Path = typer.Option(..., help="Output GraphML path"),
    scats_zip: Path = typer.Option(None, help="Optional pre-downloaded SCATS ZIP path"),
    month: str = typer.Option(None, help="Month name if downloading"),
    year: int = typer.Option(None, help="Year if downloading"),
    project_method: str = typer.Option("average", help="Projection method: average|upstream|downstream"),
):
    """Attach SCATS flows to a GraphML by mapping sites to nearest nodes and projecting to edges."""
    from .data_fetch import read_scats_zip, download_scats_zip
    G = graph_build.load_graphml(graph_in)
    if scats_zip is not None:
        df = read_scats_zip(scats_zip)
    else:
        if not (month and year):
            raise typer.BadParameter("Provide either --scats-zip or both --month and --year")
        z = download_scats_zip(month, year)
        df = read_scats_zip(z)
    site_map = read_site_coords_csv(site_coords_csv)
    df_nodes = map_sites_to_nodes(df, site_map, G).dropna(subset=["node_id"]).copy()
    df_nodes["node_id"] = df_nodes["node_id"].astype(int)
    flow_mod.attach_node_flow_series_from_df(G, df_nodes)
    flow_mod.project_node_flows_to_edges(G, method=project_method)
    graph_build.save_graphml(G, out_graph)
    typer.echo(f"Saved with flows to {out_graph}")


@app.command("generate-synth")
def generate_synth(
    graph_in: Path = typer.Option(..., help="Input GraphML path"),
    out_graph: Path = typer.Option(..., help="Output GraphML path"),
):
    """Generate synthetic edge flow series and save GraphML."""
    G = graph_build.load_graphml(graph_in)
    generate_synthetic_flows(G)
    graph_build.save_graphml(G, out_graph)
    typer.echo(f"Saved with synthetic flows to {out_graph}")


@app.command("map")
def map_command(
    place: str = typer.Option(..., help="OSM place string (e.g., 'Dublin, Ireland')"),
    out: Path = typer.Option(..., help="Output HTML path"),
    layers: str = typer.Option("all", help="Layers to include: roads, supernodes, junctions, categories, all"),
    edges_csv: Path = typer.Option(None, help="Optional path to save edges with capacity CSV"),
    with_population: bool = typer.Option(False, help="Include population capacity assignment"),
    census_path: Path = typer.Option(None, help="Path to census data file (JSON, Excel)"),
    time_of_day: str = typer.Option("day", help="Time of day for demand scaling: morning, day, evening, night"),
    force_supernodes: bool = typer.Option(False, help="Force recomputation of supernodes"),
    force_traffic_lights: bool = typer.Option(False, help="Force recomputation of traffic lights"),
    force_reprocess: bool = typer.Option(False, help="Force reprocess all cached files (census, boundaries, supernodes, etc.)"),
    use_osm_pois: bool = typer.Option(True, help="Use OSM POI data for enhanced category detection"),
    use_google_places: bool = typer.Option(True, help="Use Google Places API for business detection"),
    use_heuristics: bool = typer.Option(True, help="Use fallback heuristics for business detection"),
):
    """Create an enhanced traffic flow map with multiple layers and controls."""
    typer.echo(f"Building graph for {place}...")
    
    # Build the graph (use 18km radius for Dublin)
    use_18km_radius = "Dublin" in place
    G = graph_build.build_graph(place, use_18km_radius=use_18km_radius)
    
    # Add capacity annotations
    typer.echo("Computing road capacities...")
    G = attach_capacity_to_graph(G)
    
    # Detect traffic lights
    typer.echo("Detecting traffic lights...")
    from .traffic_lights import detect_and_cache_traffic_lights
    G = detect_and_cache_traffic_lights(G, place, force_recompute=force_traffic_lights or force_reprocess)
    
    # Save edges with capacity if requested
    if edges_csv:
        typer.echo(f"Saving edges with capacity to {edges_csv}...")
        save_edges_with_capacity(G, edges_csv)
    
    # Detect and collapse supernodes (with caching)
    typer.echo("Detecting and collapsing supernodes...")
    supernodes = detect_and_cache_supernodes(G, place, force_recompute=force_supernodes or force_reprocess)
    G = collapse_supernodes(G, supernodes)
    
    # Assign categories to nodes (enhanced with POI detection)
    typer.echo("Classifying nodes by category...")
    G = assign_categories_enhanced(G, place, use_osm=use_osm_pois, use_google=use_google_places, use_heuristics=use_heuristics)
    
    # Detect office sinks if Google Places is enabled
    if use_google_places:
        typer.echo("Detecting office sinks...")
        G = detect_office_sinks(G, place)
    
    # Annotate junctions with efficiency
    typer.echo("Computing junction efficiency...")
    G = annotate_junctions(G)
    
    # Assign population capacity if requested
    if with_population:
        typer.echo("Assigning population capacity...")
        # Use enhanced population assignment with census integration
        if census_path:
            G = assign_population_capacity_enhanced(G, census_path, force_reprocess=force_reprocess)
        else:
            # Try default census path (prefer .px file over .json)
            default_census = Path("data/raw/census/population_small_area_2022.px")
            if not default_census.exists():
                # Fallback to JSON file if .px doesn't exist
                default_census = Path("data/raw/census/population_small_area_2022.json")
            if default_census.exists():
                typer.echo("Using default census data...")
                G = assign_population_capacity_enhanced(G, default_census)
            else:
                typer.echo("No census data found, using POI-based assignment...")
                G = assign_population_capacity(G)
        
        # Print population summary
        summary = get_population_summary(G)
        typer.echo(f"Population capacity summary:")
        typer.echo(f"  Total capacity: {summary['total_capacity']}")
        typer.echo(f"  Average capacity: {summary['average_capacity']:.1f}")
        typer.echo(f"  Categories: {list(summary['categories'].keys())}")
    
    # Generate synthetic flows for visualization
    typer.echo("Generating synthetic flows...")
    generate_synthetic_flows(G)
    
    # Create enhanced map
    typer.echo(f"Creating enhanced map with layers: {layers} and time-of-day: {time_of_day}...")
    
    # Load SCAT sensor data if available
    scat_df = None
    try:
        from .scat_flow import load_scat_sensor_data
        scat_df = load_scat_sensor_data()
        if scat_df is not None and not scat_df.empty:
            typer.echo(f"Loaded {len(scat_df)} SCAT sensors")
        else:
            typer.echo("No SCAT sensor data available")
    except Exception as e:
        typer.echo(f"Could not load SCAT sensor data: {e}")
    
    save_enhanced_folium_map(G, out, layers=layers, time_of_day=time_of_day, census_data_path=census_path, scats_df=scat_df)
    
    typer.echo(f"Enhanced map saved to {out}")
    typer.echo("Open the HTML file in a web browser to view the interactive map.")


if __name__ == "__main__":
    main()


