"""Traffic Model package."""

from .load_graph import load_graph_from_csv, generate_synthetic_flows  # re-export for convenience
from .neighborhood import (
    detect_single_connection_neighborhoods,
    collapse_neighborhoods_to_supernodes,
    detect_and_collapse,
)
from .viz import save_folium_flow_map, save_enhanced_folium_map
from .data_fetch import download_scats_zip, read_scats_zip, map_sites_to_nodes, load_sample_flow, get_scats_download_links, find_scats_zip_links
from .population import assign_population_capacity, get_population_summary, DEFAULT_CAPACITY, TIME_PROFILE

__all__ = [
    "load_graph_from_csv",
    "generate_synthetic_flows",
    "detect_single_connection_neighborhoods",
    "collapse_neighborhoods_to_supernodes",
    "detect_and_collapse",
    "save_folium_flow_map",
    "save_enhanced_folium_map",
    "download_scats_zip",
    "read_scats_zip",
    "map_sites_to_nodes",
    "load_sample_flow",
    "get_scats_download_links",
    "find_scats_zip_links",
    "assign_population_capacity",
    "get_population_summary",
    "DEFAULT_CAPACITY",
    "TIME_PROFILE",
]

"""Traffic Model package.

Provides tools to build road graphs from OSM, detect neighbourhoods, simplify
into supernodes, attach flow time-series, and visualise on maps.
"""