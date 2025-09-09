from traffic_model import (
  load_graph_from_csv, generate_synthetic_flows,
  detect_and_collapse, save_folium_flow_map,
  get_scats_download_links, find_scats_zip_links,
  download_scats_zip, read_scats_zip,
)
from pathlib import Path


def print_header(title: str):
    print("\n" + "="*20 + f" {title} " + "="*20)


def main():
    print_header("Web scraping: discover SCATS ZIP links")
    pages = [
      "https://data.smartdublin.ie/datasets/traffic/SCATS/Volumes",
      "https://data.smartdublin.ie/datasets/traffic/SCATS",
    ]
    links = get_scats_download_links(pages)
    print(f"Found {len(links)} links (showing up to 5):")
    for url in links[:5]:
        print(" -", url)

    ranked = find_scats_zip_links(pages, month="January", year=2024)
    print("Top-ranked links for January 2024 (up to 3):")
    for url in ranked[:3]:
        print(" -", url)

    print_header("Download sample SCATS (Jan 2024) if available")
    try:
        zip_path = download_scats_zip("January", 2024)
        print("Downloaded:", zip_path)
        df = read_scats_zip(zip_path)
        print("SCATS shape:", df.shape)
        print("SCATS head:\n", df.head())
    except Exception as e:
        print("SCATS download/read skipped:", e)
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

        print_header("Export Folium map")
        out = Path("flow_map.html")
        save_folium_flow_map(Gc, out)
        print("Wrote:", out.resolve())
    except FileNotFoundError as e:
        print("Graph CSVs not found:", e)


if __name__ == "__main__":
    main()