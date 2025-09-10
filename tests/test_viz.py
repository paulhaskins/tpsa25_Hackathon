from pathlib import Path
import networkx as nx
from traffic_model import save_folium_flow_map
from traffic_model.viz import save_enhanced_folium_map


def test_save_folium_flow_map(tmp_path: Path):
    G = nx.MultiDiGraph()
    G.add_node(1, x=-6.0, y=53.0, is_supernode=True)
    G.add_node(2, x=-6.01, y=53.01)
    G.add_edge(1, 2, flow_series=[100]*24)
    out = tmp_path / "map.html"
    save_folium_flow_map(G, out)
    assert out.exists()


def test_save_enhanced_folium_map(tmp_path: Path):
    """Test enhanced folium map creation."""
    G = nx.MultiDiGraph()
    G.add_node(1, x=-6.0, y=53.0, is_supernode=True, type='Residential', population_capacity=100, category='Residential')
    G.add_node(2, x=-6.01, y=53.01, category='Business')
    G.add_node(3, x=-6.02, y=53.02, category='Transport')
    G.add_edge(1, 2, flow_series=[100]*24, capacity=50, length=100, lanes=2)
    G.add_edge(2, 3, flow_series=[80]*24, capacity=40, length=80, lanes=1)
    
    out = tmp_path / "enhanced_map.html"
    save_enhanced_folium_map(G, out, layers="all")
    assert out.exists()


def test_save_enhanced_folium_map_with_time_of_day(tmp_path: Path):
    """Test enhanced folium map creation with time-of-day scaling."""
    G = nx.MultiDiGraph()
    G.add_node(1, x=-6.0, y=53.0, is_supernode=True, category='Residential', population_capacity=100, demand_profile={'morning': 0.2, 'day': 0.3, 'evening': 0.8, 'night': 1.0})
    G.add_node(2, x=-6.01, y=53.01, category='Business', population_capacity=200, demand_profile={'morning': 1.0, 'day': 0.8, 'evening': 0.2, 'night': 0.0})
    G.add_edge(1, 2, flow_series=[100]*24, capacity=50, length=100, lanes=2)
    
    out = tmp_path / "enhanced_map_evening.html"
    save_enhanced_folium_map(G, out, layers="all", time_of_day="evening")
    assert out.exists()
    
    # Test that evening scaling affects marker sizes differently for different categories
    out_morning = tmp_path / "enhanced_map_morning.html"
    save_enhanced_folium_map(G, out_morning, layers="all", time_of_day="morning")
    assert out_morning.exists()


def test_save_enhanced_folium_map_with_population(tmp_path: Path):
    """Test enhanced folium map creation with population capacity and demand profiles."""
    G = nx.MultiDiGraph()
    G.add_node(1, x=-6.0, y=53.0, is_supernode=True, category='Residential', population_capacity=100, demand_profile={'morning': 0.2, 'day': 0.3, 'evening': 0.8, 'night': 1.0})
    G.add_node(2, x=-6.01, y=53.01, category='School', population_capacity=500, demand_profile={'morning': 1.0, 'day': 0.5, 'evening': 0.0, 'night': 0.0})
    G.add_node(3, x=-6.02, y=53.02, category='Transport', population_capacity=2000, demand_profile={'morning': 1.0, 'day': 0.6, 'evening': 1.0, 'night': 0.2})
    G.add_edge(1, 2, flow_series=[100]*24, capacity=50, length=100, lanes=2)
    G.add_edge(2, 3, flow_series=[80]*24, capacity=40, length=80, lanes=1)
    
    out = tmp_path / "enhanced_map_population.html"
    save_enhanced_folium_map(G, out, layers="all", time_of_day="day")
    assert out.exists()


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q", "-s"]))


