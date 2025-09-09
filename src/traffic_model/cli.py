import typer
from pathlib import Path
from . import graph_build, simplify as simplify_mod, flow as flow_mod
from .load_graph import load_graph_from_csv, generate_synthetic_flows
from .data_fetch import load_sample_flow, read_site_coords_csv, map_sites_to_nodes
from .viz import save_folium_flow_map

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


if __name__ == "__main__":
    main()


