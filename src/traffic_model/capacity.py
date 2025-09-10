"""
capacity.py - Road capacity estimation utilities.
"""

import networkx as nx
import pandas as pd
from pathlib import Path

DEFAULT_CAR_LENGTH = 4.5  # meters, approx standard car size


def compute_edge_capacity(length_m: float, lanes: int = 1, car_length: float = DEFAULT_CAR_LENGTH) -> int:
    """
    Compute maximum capacity for a road segment in terms of car units.

    Args:
        length_m (float): Road length in meters.
        lanes (int): Number of lanes (default=1).
        car_length (float): Average car length in meters.

    Returns:
        int: Maximum number of cars that can fit on the segment.
    """
    if length_m <= 0 or lanes <= 0 or car_length <= 0:
        return 0
    
    # Calculate cars per lane, then multiply by number of lanes
    cars_per_lane = int(length_m / car_length)
    total_capacity = cars_per_lane * lanes
    return total_capacity


def attach_capacity_to_graph(G: nx.Graph) -> nx.Graph:
    """
    Annotate each edge in the graph with a 'capacity' attribute.

    Args:
        G (nx.Graph): OSMnx/NetworkX road graph.

    Returns:
        nx.Graph: Graph with edge['capacity'] set.
    """
    for u, v, k, data in G.edges(keys=True, data=True):
        # Get edge length from geometry or calculate from coordinates
        length_m = data.get('length', 0.0)
        if length_m == 0.0:
            # Fallback: calculate distance from node coordinates
            u_data = G.nodes[u]
            v_data = G.nodes[v]
            if 'x' in u_data and 'y' in u_data and 'x' in v_data and 'y' in v_data:
                import math
                dx = u_data['x'] - v_data['x']
                dy = u_data['y'] - v_data['y']
                length_m = math.sqrt(dx*dx + dy*dy) * 111000  # rough conversion to meters
        
        # Get number of lanes, default to 1
        lanes = data.get('lanes', 1)
        if isinstance(lanes, str):
            try:
                lanes = int(lanes)
            except (ValueError, TypeError):
                lanes = 1
        elif isinstance(lanes, list):
            # If lanes is a list, take the maximum value
            try:
                lanes = max(int(lane) for lane in lanes if lane)
            except (ValueError, TypeError):
                lanes = 1
        
        # Ensure lanes is an integer and at least 1
        try:
            lanes = max(1, int(lanes))
        except (ValueError, TypeError):
            lanes = 1
        
        # Calculate and set capacity
        capacity = compute_edge_capacity(length_m, lanes)
        G.edges[u, v, k]['capacity'] = capacity
    
    return G


def save_edges_with_capacity(G: nx.Graph, output_path: Path) -> None:
    """
    Save edges with capacity information to CSV file.

    Args:
        G (nx.Graph): Graph with capacity annotations.
        output_path (Path): Path to save the CSV file.
    """
    edges_data = []
    
    for u, v, k, data in G.edges(keys=True, data=True):
        edge_info = {
            'u': u,
            'v': v,
            'key': k,
            'length': data.get('length', 0.0),
            'lanes': data.get('lanes', 1),
            'capacity': data.get('capacity', 0),
            'name': data.get('name', ''),
            'highway': data.get('highway', ''),
        }
        edges_data.append(edge_info)
    
    df = pd.DataFrame(edges_data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
