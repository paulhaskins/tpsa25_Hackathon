from pathlib import Path
import osmnx as ox
import networkx as nx
import numpy as np


def build_graph(place: str, use_18km_radius: bool = False) -> nx.MultiDiGraph:
    """
    Build a drivable street graph for a place using OSMnx.
    
    Args:
        place: Place name for OSMnx graph
        use_18km_radius: If True and place is Dublin, use 18km radius bounding box
    """
    if use_18km_radius and "Dublin" in place:
        return build_dublin_18km_graph()
    else:
        G = ox.graph_from_place(place, network_type="drive")
        return G


def build_dublin_18km_graph() -> nx.MultiDiGraph:
    """
    Build a graph for Dublin using an 18km radius from city center.
    
    Returns:
        MultiDiGraph with roads and junctions within 18km of Dublin center
    """
    # Dublin city center coordinates (Spire of Dublin)
    dublin_center_lat = 53.3498
    dublin_center_lon = -6.2603
    radius_km = 18
    
    print(f"Building Dublin graph with 18km radius from center")
    
    # Try different approaches to get the graph
    try:
        # First try: use graph_from_point
        G = ox.graph_from_point((dublin_center_lat, dublin_center_lon), dist=radius_km*1000, network_type="drive")
        print(f"Successfully built graph using graph_from_point")
    except Exception as e:
        print(f"graph_from_point failed: {e}")
        try:
            # Second try: use graph_from_place with a more specific area
            G = ox.graph_from_place("Dublin, Ireland", network_type="drive")
            print(f"Successfully built graph using graph_from_place")
        except Exception as e2:
            print(f"graph_from_place also failed: {e2}")
            # Fallback: use a simple bounding box approach
            lat_radius = radius_km / 111.0
            lon_radius = radius_km / (111.0 * np.cos(np.radians(dublin_center_lat)))
            north = dublin_center_lat + lat_radius
            south = dublin_center_lat - lat_radius
            east = dublin_center_lon + lon_radius
            west = dublin_center_lon - lon_radius
            
            G = ox.graph_from_bbox(north, south, east, west, network_type="drive")
            print(f"Successfully built graph using graph_from_bbox")
    
    # Filter nodes and edges to ensure they're within the 18km radius
    nodes_to_remove = []
    for node, data in G.nodes(data=True):
        if 'y' in data and 'x' in data:
            # Calculate distance from Dublin center
            lat, lon = data['y'], data['x']
            distance = np.sqrt(
                (lat - dublin_center_lat)**2 + 
                (lon - dublin_center_lon)**2
            ) * 111.0  # Convert to km
            
            if distance > radius_km:
                nodes_to_remove.append(node)
    
    # Remove nodes outside the radius
    G.remove_nodes_from(nodes_to_remove)
    
    print(f"Built graph with {len(G.nodes())} nodes and {len(G.edges())} edges within 18km of Dublin center")
    
    return G


def save_graphml(G: nx.MultiDiGraph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(G, filepath=str(path))


def load_graphml(path: Path) -> nx.MultiDiGraph:
    return ox.load_graphml(filepath=str(path))


