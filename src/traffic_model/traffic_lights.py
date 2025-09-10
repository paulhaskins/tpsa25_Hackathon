"""Traffic light detection and annotation for OSMnx graphs."""

import osmnx as ox
import networkx as nx
import json
from pathlib import Path
from typing import Dict, Any, Set, Optional


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


def save_traffic_lights_to_file(traffic_light_nodes: Set[Any], place: str, 
                               output_dir: Path = Path("data/processed")) -> Path:
    """Save traffic light nodes to a JSON cache file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create filename from place name
    place_key = place.replace(" ", "_").replace(",", "").lower()
    cache_file = output_dir / f"traffic_lights_{place_key}.json"
    
    # Convert set to list for JSON serialization
    data = {
        "place": place,
        "traffic_light_nodes": list(traffic_light_nodes),
        "count": len(traffic_light_nodes)
    }
    
    with open(cache_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    return cache_file


def load_traffic_lights_from_file(place: str, 
                                 output_dir: Path = Path("data/processed")) -> Optional[Set[Any]]:
    """Load traffic light nodes from cache file."""
    place_key = place.replace(" ", "_").replace(",", "").lower()
    cache_file = output_dir / f"traffic_lights_{place_key}.json"
    
    if not cache_file.exists():
        return None
    
    try:
        with open(cache_file, 'r') as f:
            data = json.load(f)
        
        # Verify this is for the same place
        if data.get("place") != place:
            return None
        
        # Convert list back to set
        return set(data.get("traffic_light_nodes", []))
        
    except (json.JSONDecodeError, KeyError, FileNotFoundError):
        return None


def detect_and_cache_traffic_lights(G: nx.MultiDiGraph, place: str, 
                                   force_recompute: bool = False,
                                   output_dir: Path = Path("data/processed")) -> nx.MultiDiGraph:
    """Detect traffic lights with caching support."""
    if not force_recompute:
        # Try to load from cache first
        cached_traffic_lights = load_traffic_lights_from_file(place, output_dir)
        if cached_traffic_lights is not None:
            print(f"Loaded cached traffic lights for {place}")
            # Apply cached traffic light annotations
            for node in G.nodes():
                G.nodes[node]['has_traffic_light'] = node in cached_traffic_lights
            print(f"Annotated {len(cached_traffic_lights)} nodes with cached traffic lights")
            return G
    
    # Compute new traffic lights
    print(f"Detecting traffic lights for {place}...")
    
    try:
        # Query for traffic signals
        traffic_signals = ox.features_from_place(
            place, 
            tags={'highway': 'traffic_signals'}
        )
        
        if len(traffic_signals) == 0:
            print("No traffic signals found in OSM data")
            # Initialize all nodes as having no traffic lights
            for node in G.nodes():
                G.nodes[node]['has_traffic_light'] = False
            # Save empty result to cache
            save_traffic_lights_to_file(set(), place, output_dir)
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
        
        # Save to cache
        if traffic_light_nodes:
            cache_path = save_traffic_lights_to_file(traffic_light_nodes, place, output_dir)
            print(f"Saved traffic lights to {cache_path}")
        
        return G
        
    except Exception as e:
        print(f"Error detecting traffic lights: {e}")
        # Initialize all nodes as having no traffic lights
        for node in G.nodes():
            G.nodes[node]['has_traffic_light'] = False
        return G
