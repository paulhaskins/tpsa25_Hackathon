from pathlib import Path
import csv
import networkx as nx
from traffic_model import load_graph_from_csv


def write_csv(path: Path, rows):
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerows(rows)


def test_load_graph_and_capacity(tmp_path: Path):
    nodes_csv = tmp_path / "nodes.csv"
    edges_csv = tmp_path / "edges.csv"

    write_csv(nodes_csv, [
        ["node_id", "lat", "lon"],
        [1, 53.0, -6.0],
        [2, 53.001, -6.001],
    ])
    write_csv(edges_csv, [
        ["u", "v", "lanes", "length"],
        [1, 2, 2, 100.0],
        [2, 1, "2;3", 100.0],
    ])

    G = load_graph_from_csv(nodes_csv, edges_csv, edges_out_csv=tmp_path / "edges_out.csv")
    assert isinstance(G, nx.MultiDiGraph)
    assert G.number_of_nodes() == 2
    assert G.number_of_edges() == 2
    # capacity lanes*1800 -> 3600 for lanes=2; and max(2,3)=3 -> 5400
    caps = sorted(e[3]["capacity"] for e in G.edges(keys=True, data=True))
    assert caps == [3600, 5400]
    assert (tmp_path / "edges_out.csv").exists()


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q", "-s"]))


