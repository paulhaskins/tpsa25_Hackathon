"""Traffic Model package."""

from .load_graph import load_graph_from_csv, generate_synthetic_flows  # re-export for convenience
from .neighborhood import (
    detect_single_connection_neighborhoods,
    collapse_neighborhoods_to_supernodes,
    detect_and_collapse,
)
from .viz import save_folium_flow_map
from .population import (
    load_census_geometries,
    load_landuse_mask,
    load_pois_or_jobs,
    build_node_catchments,
    dasymetric_allocate_population,
    compute_sink_attraction,
    rollup_to_supernodes,
    impedance_matrix,
    expected_flows_gravity,
    calibrate_gravity_with_scats,
    estimate_sources_sinks_and_flows,
    DEFAULT_TIME_BINS as POP_DEFAULT_TIME_BINS,
    POI_WEIGHTS,
)
from .data_fetch import download_scats_zip, read_scats_zip, map_sites_to_nodes, load_sample_flow, get_scats_download_links, find_scats_zip_links

__all__ = [
    "load_graph_from_csv",
    "generate_synthetic_flows",
    "detect_single_connection_neighborhoods",
    "collapse_neighborhoods_to_supernodes",
    "detect_and_collapse",
    "save_folium_flow_map",
    "load_census_geometries",
    "load_landuse_mask",
    "load_pois_or_jobs",
    "build_node_catchments",
    "dasymetric_allocate_population",
    "compute_sink_attraction",
    "rollup_to_supernodes",
    "impedance_matrix",
    "expected_flows_gravity",
    "calibrate_gravity_with_scats",
    "estimate_sources_sinks_and_flows",
    "POI_WEIGHTS",
    "download_scats_zip",
    "read_scats_zip",
    "map_sites_to_nodes",
    "load_sample_flow",
    "get_scats_download_links",
    "find_scats_zip_links",
]

"""Traffic Model package.

Provides tools to build road graphs from OSM, detect neighbourhoods, simplify
into supernodes, attach flow time-series, and visualise on maps.
"""

__all__ = [
    "cli",
]


