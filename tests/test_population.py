"""Tests for population capacity assignment functionality."""

import networkx as nx
import pandas as pd
from pathlib import Path
import tempfile
from traffic_model.population import (
    assign_population_capacity,
    assign_population_capacity_enhanced,
    estimate_poi_capacity,
    assign_heuristic_capacity,
    assign_demand_profile,
    get_population_summary,
    load_census_data,
    assign_population_from_census,
    DEFAULT_CAPACITY,
    TIME_PROFILE,
    POI_CAPACITY_ESTIMATES,
)


def test_assign_heuristic_capacity():
    """Test heuristic capacity assignment."""
    assert assign_heuristic_capacity("Residential") == DEFAULT_CAPACITY["Residential"]
    assert assign_heuristic_capacity("Business") == DEFAULT_CAPACITY["Business"]
    assert assign_heuristic_capacity("School") == DEFAULT_CAPACITY["School"]
    assert assign_heuristic_capacity("Hospital") == DEFAULT_CAPACITY["Hospital"]
    assert assign_heuristic_capacity("Transport") == DEFAULT_CAPACITY["Transport"]
    assert assign_heuristic_capacity("Unknown") == DEFAULT_CAPACITY["Other"]


def test_assign_demand_profile():
    """Test demand profile assignment."""
    residential_profile = assign_demand_profile("Residential")
    assert "morning" in residential_profile
    assert "day" in residential_profile
    assert "evening" in residential_profile
    assert "night" in residential_profile
    assert residential_profile["morning"] == 0.2
    assert residential_profile["evening"] == 0.8
    
    business_profile = assign_demand_profile("Business")
    assert business_profile["morning"] == 1.0
    assert business_profile["night"] == 0.0
    
    unknown_profile = assign_demand_profile("Unknown")
    assert unknown_profile == TIME_PROFILE["Other"]


def test_estimate_poi_capacity():
    """Test POI-based capacity estimation."""
    # Test residential POI
    residential_data = {"amenity": "house", "building": "residential"}
    capacity = estimate_poi_capacity(residential_data)
    assert capacity > 0
    
    # Test business POI
    business_data = {"amenity": "shop", "landuse": "commercial"}
    capacity = estimate_poi_capacity(business_data)
    assert capacity > 0
    
    # Test transport POI
    transport_data = {"public_transport": "station", "amenity": "bus_station"}
    capacity = estimate_poi_capacity(transport_data)
    assert capacity >= POI_CAPACITY_ESTIMATES["bus_station"]
    
    # Test school POI
    school_data = {"amenity": "school"}
    capacity = estimate_poi_capacity(school_data)
    assert capacity >= POI_CAPACITY_ESTIMATES["school"]
    
    # Test hospital POI
    hospital_data = {"amenity": "hospital"}
    capacity = estimate_poi_capacity(hospital_data)
    assert capacity >= POI_CAPACITY_ESTIMATES["hospital"]
    
    # Test empty data
    empty_data = {}
    capacity = estimate_poi_capacity(empty_data)
    assert capacity == 1  # Minimum capacity


def test_assign_population_capacity():
    """Test population capacity assignment to graph nodes."""
    # Create test graph
    G = nx.MultiDiGraph()
    G.add_node(1, x=-6.0, y=53.0, category="Residential", amenity="house")
    G.add_node(2, x=-6.01, y=53.01, category="Business", amenity="shop")
    G.add_node(3, x=-6.02, y=53.02, category="School", amenity="school")
    G.add_node(4, x=-6.03, y=53.03, category="Hospital", amenity="hospital")
    G.add_node(5, x=-6.04, y=53.04, category="Transport", public_transport="station")
    
    # Assign population capacity
    G_with_pop = assign_population_capacity(G)
    
    # Check that all nodes have population capacity
    for node, data in G_with_pop.nodes(data=True):
        assert 'population_capacity' in data
        assert data['population_capacity'] > 0
        assert 'demand_profile' in data
        assert isinstance(data['demand_profile'], dict)
        assert len(data['demand_profile']) > 0
    
    # Check specific categories
    residential_node = next(n for n, d in G_with_pop.nodes(data=True) if d.get('category') == 'Residential')
    business_node = next(n for n, d in G_with_pop.nodes(data=True) if d.get('category') == 'Business')
    
    assert G_with_pop.nodes[residential_node]['population_capacity'] > 0
    assert G_with_pop.nodes[business_node]['population_capacity'] > 0


def test_assign_population_capacity_with_census():
    """Test population capacity assignment with census data."""
    # Create test census data
    census_data = pd.DataFrame({
        'area': ['SA001', 'SA002', 'SA003'],
        'population': [100, 200, 150]
    })
    
    # Create temporary census file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        census_data.to_csv(f.name, index=False)
        census_path = f.name
    
    try:
        # Create test graph
        G = nx.MultiDiGraph()
        G.add_node(1, x=-6.0, y=53.0, category="Residential")
        G.add_node(2, x=-6.01, y=53.01, category="Business")
        
        # Assign population capacity with census data
        G_with_pop = assign_population_capacity(G, census_path)
        
        # Check that nodes have population capacity
        for node, data in G_with_pop.nodes(data=True):
            assert 'population_capacity' in data
            assert data['population_capacity'] > 0
            assert 'demand_profile' in data
    
    finally:
        # Clean up temporary file
        Path(census_path).unlink(missing_ok=True)


def test_get_population_summary():
    """Test population summary generation."""
    # Create test graph with population capacity
    G = nx.MultiDiGraph()
    G.add_node(1, category="Residential", population_capacity=100, demand_profile={"morning": 0.2})
    G.add_node(2, category="Business", population_capacity=200, demand_profile={"morning": 1.0})
    G.add_node(3, category="Residential", population_capacity=150, demand_profile={"morning": 0.2})
    G.add_node(4, category="School", population_capacity=500, demand_profile={"morning": 1.0})
    
    summary = get_population_summary(G)
    
    # Check summary structure
    assert "total_capacity" in summary
    assert "average_capacity" in summary
    assert "median_capacity" in summary
    assert "min_capacity" in summary
    assert "max_capacity" in summary
    assert "categories" in summary
    
    # Check values
    assert summary["total_capacity"] == 950  # 100 + 200 + 150 + 500
    assert summary["average_capacity"] == 237.5  # 950 / 4
    assert summary["min_capacity"] == 100
    assert summary["max_capacity"] == 500
    
    # Check category breakdown
    assert "Residential" in summary["categories"]
    assert "Business" in summary["categories"]
    assert "School" in summary["categories"]
    
    residential_stats = summary["categories"]["Residential"]
    assert residential_stats["count"] == 2
    assert residential_stats["total"] == 250  # 100 + 150
    assert residential_stats["average"] == 125.0  # 250 / 2


def test_population_capacity_smoke_test():
    """Smoke test for the complete population capacity workflow."""
    # Create a toy graph with different node types
    G = nx.MultiDiGraph()
    G.add_node(1, x=-6.0, y=53.0, category="Residential", amenity="house")
    G.add_node(2, x=-6.01, y=53.01, category="Business", amenity="shop")
    G.add_node(3, x=-6.02, y=53.02, category="School", amenity="school")
    
    # Run the complete workflow
    G_result = assign_population_capacity(G)
    
    # Verify results
    assert len(G_result.nodes) == 3
    
    for node, data in G_result.nodes(data=True):
        # Check required attributes
        assert 'population_capacity' in data
        assert 'demand_profile' in data
        assert 'category' in data
        
        # Check data types and values
        assert isinstance(data['population_capacity'], int)
        assert data['population_capacity'] > 0
        assert isinstance(data['demand_profile'], dict)
        assert len(data['demand_profile']) > 0
        
        # Check that demand profile has expected time periods
        expected_periods = ["morning", "day", "evening", "night"]
        for period in expected_periods:
            assert period in data['demand_profile']
            assert 0 <= data['demand_profile'][period] <= 1
    
    # Test summary generation
    summary = get_population_summary(G_result)
    assert summary["total_capacity"] > 0
    assert len(summary["categories"]) > 0


def test_assign_population_capacity_enhanced():
    """Test enhanced population capacity assignment with census integration."""
    # Create test graph
    G = nx.MultiDiGraph()
    G.add_node(1, x=-6.0, y=53.0, category="Residential")
    G.add_node(2, x=-6.01, y=53.01, category="Business")
    G.add_node(3, x=-6.02, y=53.02, category="School")
    
    # Test without census data (should fall back to POI/heuristic)
    G_result = assign_population_capacity_enhanced(G)
    
    # Check that all nodes have population capacity
    for node, data in G_result.nodes(data=True):
        assert 'population_capacity' in data
        assert data['population_capacity'] > 0
        assert 'demand_profile' in data
        assert isinstance(data['demand_profile'], dict)


def test_enhanced_population_with_census_data(tmp_path: Path):
    """Test enhanced population assignment with mock census data."""
    # Create mock census data
    census_data = pd.DataFrame({
        'Small Area': ['SA001', 'SA002', 'SA003'],
        'population': [100, 200, 150]
    })
    
    # Create temporary census file
    census_path = tmp_path / "test_census.json"
    census_data.to_json(census_path, orient='records')
    
    # Create test graph
    G = nx.MultiDiGraph()
    G.add_node(1, x=-6.0, y=53.0, category="Residential")
    G.add_node(2, x=-6.01, y=53.01, category="Business")
    
    # Test enhanced assignment (will fall back to POI/heuristic since no real census structure)
    G_result = assign_population_capacity_enhanced(G, census_path)
    
    # Check that nodes have population capacity
    for node, data in G_result.nodes(data=True):
        assert 'population_capacity' in data
        assert data['population_capacity'] > 0
        assert 'demand_profile' in data


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q", "-s"]))
