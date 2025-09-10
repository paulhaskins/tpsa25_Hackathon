"""
junctions.py - Junction analysis and efficiency assignment.
"""

import networkx as nx
from typing import Dict, Any


def compute_junction_efficiency(G: nx.Graph, node_id: int) -> float:
    """
    Compute efficiency of a junction (traffic light metaphor).

    Args:
        G (nx.Graph): Road graph.
        node_id (int): Node ID of the junction.

    Returns:
        float: Efficiency factor (0 < eff <= 1).
    """
    if node_id not in G.nodes:
        return 1.0
    
    # Get node degree (number of connections)
    degree = G.degree(node_id)
    
    # Base efficiency on degree - more connections = lower efficiency
    if degree <= 2:
        # Simple intersection or dead end
        base_efficiency = 1.0
    elif degree == 3:
        # T-junction
        base_efficiency = 0.9
    elif degree == 4:
        # Standard 4-way intersection
        base_efficiency = 0.8
    elif degree <= 6:
        # Complex intersection
        base_efficiency = 0.7
    else:
        # Very complex intersection (roundabout, etc.)
        base_efficiency = 0.6
    
    # Check for SCATS data if available
    node_data = G.nodes[node_id]
    if 'scats_id' in node_data or 'junction_id' in node_data:
        # If SCATS data is available, we could use more sophisticated efficiency calculation
        # For now, apply a small bonus for having traffic management
        return min(1.0, base_efficiency + 0.1)
    
    return base_efficiency


def annotate_junctions(G: nx.Graph) -> nx.Graph:
    """
    Annotate junction nodes with efficiency values.

    Args:
        G (nx.Graph): Road graph.

    Returns:
        nx.Graph: Graph with node['efficiency'] set.
    """
    for node in G.nodes():
        # Only annotate nodes with degree >= 3 (junctions)
        if G.degree(node) >= 3:
            efficiency = compute_junction_efficiency(G, node)
            G.nodes[node]['efficiency'] = efficiency
        else:
            # Non-junction nodes get efficiency 1.0
            G.nodes[node]['efficiency'] = 1.0
    
    return G
