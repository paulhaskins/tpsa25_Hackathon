"""Data ingestion utilities for traffic modelling.

Includes:
- ckan_client: minimal CKAN Action API wrapper
- scats: Smart Dublin SCATS discovery and loader
- tii: Transport Infrastructure Ireland utilities
- normalize: helpers to standardize and align data
- cache: simple URL cache index
"""

from .ckan_client import CKANClient, list_resource_downloads  # noqa: F401
from .scats import (  # noqa: F401
    discover_scats_resources,
    rank_resources,
    download_zip,
    read_scats_zip,
    load_month,
)
from .tii import fetch_tii_portal_metadata, load_tii_counts_export  # noqa: F401
from .normalize import (  # noqa: F401
    resample_hourly,
    clip_negatives,
    drop_sparse,
    merge_sites_with_graph,
    to_flow_series,
)
from .cache import get_cached, put_cached  # noqa: F401

__all__ = [
    "CKANClient",
    "list_resource_downloads",
    "discover_scats_resources",
    "rank_resources",
    "download_zip",
    "read_scats_zip",
    "load_month",
    "fetch_tii_portal_metadata",
    "load_tii_counts_export",
    "resample_hourly",
    "clip_negatives",
    "drop_sparse",
    "merge_sites_with_graph",
    "to_flow_series",
    "get_cached",
    "put_cached",
]


