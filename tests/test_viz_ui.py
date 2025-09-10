"""
test_viz_ui.py - Smoke tests for UI/UX functionality.
"""

import networkx as nx
from pathlib import Path
import tempfile
import os
from src.traffic_model.viz import save_enhanced_folium_map, COLORS


def test_ui_controls_and_legend():
    """Test that map controls and legend are properly positioned and colored."""
    # Create a tiny test graph
    G = nx.MultiDiGraph()
    
    # Add a few test nodes with coordinates
    G.add_node(1, x=-6.2603, y=53.3498, category='Residential', population_capacity=100)  # Dublin city center
    G.add_node(2, x=-6.2503, y=53.3598, category='Business', population_capacity=500)
    G.add_node(3, x=-6.2703, y=53.3398, category='School', population_capacity=300)
    G.add_node(4, x=-6.2403, y=53.3698, category='Hospital', population_capacity=200)
    
    # Add some edges
    G.add_edge(1, 2, length=1000, capacity=100)
    G.add_edge(2, 3, length=1500, capacity=150)
    G.add_edge(3, 4, length=2000, capacity=200)
    
    # Mark one node as supernode
    G.nodes[1]['is_supernode'] = True
    G.nodes[1]['exits_count'] = 2
    G.nodes[1]['member_count'] = 5
    
    # Add traffic light info to one node
    G.nodes[2]['has_traffic_light'] = True
    G.nodes[2]['efficiency'] = 0.8
    
    # Create temporary HTML file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
        temp_html = f.name
    
    try:
        # Generate the map
        save_enhanced_folium_map(
            G, 
            temp_html, 
            layers="all", 
            time_of_day="morning"
        )
        
        # Read the generated HTML
        with open(temp_html, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Test 1: LayerControl is positioned top-right
        assert 'position="topright"' in html_content or 'leaflet-top leaflet-right' in html_content
        
        # Test 2: Legend is bottom-right positioned
        assert 'bottom: 50px; right: 50px' in html_content
        
        # Test 3: Legend shows correct object types and colors
        assert 'Object Types' in html_content
        assert 'Supernode' in html_content
        assert 'Junction' in html_content
        assert 'Source' in html_content
        assert 'Sink' in html_content
        
        # Test 4: Colors match the unified color scheme
        assert COLORS['supernode'] in html_content  # #3B82F6
        assert COLORS['junction'] in html_content   # #F59E0B
        assert COLORS['source'] in html_content     # #10B981
        assert COLORS['sink'] in html_content       # #EF4444
        
        # Test 5: FeatureGroups exist for the four object types
        assert 'Supernodes' in html_content
        assert 'Junctions' in html_content
        assert 'Sources' in html_content
        assert 'Sinks' in html_content
        
        # Test 6: Clean popups are present (no raw table dumps)
        assert '<table' not in html_content or html_content.count('<table') < 2  # Allow minimal tables
        
        # Test 7: Popup content is clean and formatted
        assert 'font-family: Arial' in html_content
        assert 'background-color: #f8f9fa' in html_content
        
        print("✓ All UI/UX tests passed!")
        
    finally:
        # Clean up
        if os.path.exists(temp_html):
            os.unlink(temp_html)


def test_color_consistency():
    """Test that colors are consistent across the application."""
    # Test that COLORS dictionary has all required object types
    required_colors = ['supernode', 'junction', 'source', 'sink']
    for color_type in required_colors:
        assert color_type in COLORS
        assert COLORS[color_type].startswith('#')
        assert len(COLORS[color_type]) == 7  # Valid hex color
    
    # Test that colors are different
    color_values = list(COLORS.values())
    assert len(set(color_values)) == len(color_values), "All colors should be unique"
    
    print("✓ Color consistency tests passed!")


def test_popup_templates():
    """Test that popup templates are clean and well-formatted."""
    from src.traffic_model.viz import _supernode_popup_html, _junction_popup_html, _source_popup_html, _sink_popup_html
    
    # Test supernode popup
    supernode_data = {
        'name': 'Test Supernode',
        'exits_count': 2,
        'member_count': 5,
        'category': 'Residential',
        'population_capacity': 100,
        'demand_profile': {'morning': 0.8, 'day': 0.5}
    }
    supernode_popup = _supernode_popup_html(1, supernode_data)
    assert 'Test Supernode' in supernode_popup
    assert 'Exits: 2' in supernode_popup
    assert 'Members: 5' in supernode_popup
    assert '<table' not in supernode_popup  # No raw tables
    
    # Test junction popup
    junction_data = {
        'degree': 4,
        'has_traffic_light': True,
        'efficiency': 0.8
    }
    junction_popup = _junction_popup_html(2, junction_data)
    assert 'Junction 2' in junction_popup
    assert 'Degree: 4' in junction_popup
    assert 'Traffic Light: Yes' in junction_popup
    assert 'Efficiency: 0.80' in junction_popup
    
    # Test source popup
    source_data = {
        'population_capacity': 150,
        'demand_profile': {'morning': 1.0, 'day': 0.3}
    }
    source_popup = _source_popup_html(3, source_data)
    assert 'Source 3' in source_popup
    assert 'Population Capacity: 150' in source_popup
    assert 'Source (Residential)' in source_popup
    
    # Test sink popup
    sink_data = {
        'name': 'Test Office',
        'place_type': 'office',
        'population_capacity': 200,
        'sink_attraction_morning': 1.0,
        'sink_attraction_day': 0.8
    }
    sink_popup = _sink_popup_html(4, sink_data)
    assert 'Test Office' in sink_popup
    assert 'Sink (Office)' in sink_popup
    assert 'Person Capacity: 200' in sink_popup
    
    print("✓ Popup template tests passed!")


if __name__ == "__main__":
    test_ui_controls_and_legend()
    test_color_consistency()
    test_popup_templates()
    print("All UI tests completed successfully!")
