"""Traffic light detection and annotation for OSMnx graphs."""

import osmnx as ox
import networkx as nx
from typing import Dict, Any


def detect_traffic_lights(G: nx.MultiDiGraph, place: str) -> nx.MultiDiGraph:
    """Detect traffic lights from OSM data and annotate graph nodes."""
    try:
        # Query for traffic signals
        print(f"Detecting traffic lights for {place}...")
        
        # Get traffic signals as points
        traffic_signals = ox.features_from_place(
            place, 
            tags={'highway': 'traffic_signals'}
        )
        
        if len(traffic_signals) == 0:
            print("No traffic signals found in OSM data")
            return G
        
        print(f"Found {len(traffic_signals)} traffic signals")
        
        # Initialize all nodes as having no traffic lights
        for node in G.nodes():
            G.nodes[node]['has_traffic_light'] = False
        
        # Find nearest graph nodes to traffic signals
        traffic_light_nodes = set()
        
        for idx, signal in traffic_signals.iterrows():
            if signal.geometry is not None:
                # Get the nearest node to this traffic signal
                nearest_node = ox.nearest_nodes(
                    G, 
                    signal.geometry.x, 
                    signal.geometry.y
                )
                if nearest_node is not None:
                    G.nodes[nearest_node]['has_traffic_light'] = True
                    traffic_light_nodes.add(nearest_node)
        
        print(f"Annotated {len(traffic_light_nodes)} nodes with traffic lights")
        return G
        
    except Exception as e:
        print(f"Error detecting traffic lights: {e}")
        # Initialize all nodes as having no traffic lights
        for node in G.nodes():
            G.nodes[node]['has_traffic_light'] = False
        return G


def get_traffic_light_info(node_data: Dict[str, Any]) -> str:
    """Get traffic light information for popup display."""
    has_light = node_data.get('has_traffic_light', False)
    return "Yes" if has_light else "No"
