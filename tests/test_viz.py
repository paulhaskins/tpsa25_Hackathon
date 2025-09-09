from pathlib import Path
import networkx as nx
from traffic_model import save_folium_flow_map


def test_save_folium_flow_map(tmp_path: Path):
    G = nx.MultiDiGraph()
    G.add_node(1, x=-6.0, y=53.0, is_supernode=True)
    G.add_node(2, x=-6.01, y=53.01)
    G.add_edge(1, 2, flow_series=[100]*24)
    out = tmp_path / "map.html"
    save_folium_flow_map(G, out)
    assert out.exists()


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q", "-s"]))


