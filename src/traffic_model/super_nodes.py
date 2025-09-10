"""
supernodes.py - Collapse neighborhoods into supernodes.
"""

import networkx as nx
from typing import Dict, Any, List, Set, Optional
import numpy as np
import json
from pathlib import Path


def detect_supernodes(G: nx.Graph, threshold: int = 2) -> Dict[int, Any]:
    """
    Identify neighborhoods with limited exits and treat them as supernodes.

    Args:
        G (nx.Graph): Road graph.
        threshold (int): Maximum number of exits allowed to qualify as a supernode.

    Returns:
        Dict[int, Any]: Mapping of node_id -> supernode info.
    """
    # Use the enhanced neighborhood detection from neighborhood.py
    from .neighborhood import detect_limited_connection_neighborhoods
    
    neighborhoods = detect_limited_connection_neighborhoods(G, max_connections=threshold)
    supernodes = {}
    
    for i, neighborhood in enumerate(neighborhoods):
        # Find the node with the most connections to outside (entry/exit point)
        entry_node = None
        max_external_connections = 0
        
        for node in neighborhood:
            external_connections = 0
            for neighbor in G.neighbors(node):
                if neighbor not in neighborhood:
                    external_connections += 1
            
            if external_connections > max_external_connections:
                max_external_connections = external_connections
                entry_node = node
        
        if entry_node is not None:
            # Calculate population capacity based on neighborhood size
            population_capacity = len(neighborhood) * 10  # Rough estimate
            
            # Determine type based on OSM tags or default to Residential
            node_type = "Residential"  # Default
            if entry_node in G.nodes:
                node_data = G.nodes[entry_node]
                # Check for business/transport indicators
                if any(tag in str(node_data).lower() for tag in ['shop', 'office', 'business', 'commercial']):
                    node_type = "Business"
                elif any(tag in str(node_data).lower() for tag in ['station', 'stop', 'transport', 'bus', 'train']):
                    node_type = "Transport"
                elif any(tag in str(node_data).lower() for tag in ['school', 'university', 'college']):
                    node_type = "School"
                elif any(tag in str(node_data).lower() for tag in ['hospital', 'clinic', 'medical']):
                    node_type = "Hospital"
            
            supernodes[entry_node] = {
                'type': node_type,
                'population_capacity': population_capacity,
                'members': list(neighborhood),
                'entry_node': entry_node
            }
    
    return supernodes


def collapse_supernodes(G: nx.Graph, supernodes: Dict[int, Any]) -> nx.Graph:
    """
    Collapse identified supernodes into single representative nodes.

    Args:
        G (nx.Graph): Road graph.
        supernodes (dict): Mapping from detect_supernodes().

    Returns:
        nx.Graph: Modified graph with supernodes collapsed.
    """
    # Use the existing neighborhood collapse functionality
    from .neighborhood import collapse_neighborhoods_to_supernodes
    
    # Convert supernodes dict to neighborhoods list format
    neighborhoods = []
    for entry_node, info in supernodes.items():
        neighborhoods.append(set(info['members']))
    
    # Collapse using existing function
    G_collapsed = collapse_neighborhoods_to_supernodes(G, neighborhoods)
    
    # Add supernode-specific attributes
    for node, data in G_collapsed.nodes(data=True):
        if data.get('is_supernode'):
            # Find the corresponding supernode info
            for entry_node, info in supernodes.items():
                if entry_node in data.get('members', []):
                    data['type'] = info['type']
                    data['population_capacity'] = info['population_capacity']
                    break
    
    return G_collapsed


def save_supernodes_to_file(supernodes: Dict[int, Any], place: str, output_dir: Path = Path("data/processed")) -> Path:
    """Save supernodes to a JSON file for reuse."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a safe filename from place name
    safe_place = "".join(c for c in place if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_place = safe_place.replace(' ', '_').lower()
    
    filename = f"supernodes_{safe_place}.json"
    filepath = output_dir / filename
    
    # Convert sets to lists for JSON serialization
    serializable_supernodes = {}
    for node_id, info in supernodes.items():
        serializable_info = info.copy()
        if 'members' in serializable_info and isinstance(serializable_info['members'], set):
            serializable_info['members'] = list(serializable_info['members'])
        serializable_supernodes[str(node_id)] = serializable_info
    
    with open(filepath, 'w') as f:
        json.dump(serializable_supernodes, f, indent=2)
    
    return filepath


def load_supernodes_from_file(place: str, input_dir: Path = Path("data/processed")) -> Optional[Dict[int, Any]]:
    """Load supernodes from a JSON file if it exists."""
    # Create a safe filename from place name
    safe_place = "".join(c for c in place if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_place = safe_place.replace(' ', '_').lower()
    
    filename = f"supernodes_{safe_place}.json"
    filepath = input_dir / filename
    
    if not filepath.exists():
        return None
    
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Convert back to proper types
        supernodes = {}
        for node_id_str, info in data.items():
            node_id = int(node_id_str)
            if 'members' in info and isinstance(info['members'], list):
                info['members'] = set(info['members'])
            supernodes[node_id] = info
        
        return supernodes
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        print(f"Error loading supernodes from {filepath}: {e}")
        return None


def detect_and_cache_supernodes(G: nx.Graph, place: str, force_recompute: bool = False, 
                               output_dir: Path = Path("data/processed")) -> Dict[int, Any]:
    """Detect supernodes with caching support."""
    if not force_recompute:
        # Try to load from cache first
        cached_supernodes = load_supernodes_from_file(place, output_dir)
        if cached_supernodes is not None:
            print(f"Loaded cached supernodes for {place}")
            return cached_supernodes
    
    # Compute new supernodes
    print(f"Computing supernodes for {place}...")
    supernodes = detect_supernodes(G)
    
    # Save to cache
    if supernodes:
        cache_path = save_supernodes_to_file(supernodes, place, output_dir)
        print(f"Saved supernodes to {cache_path}")
    
    return supernodes


__all__ = [
    "detect_supernodes",
    "collapse_supernodes", 
    "save_supernodes_to_file",
    "load_supernodes_from_file",
    "detect_and_cache_supernodes",
]
