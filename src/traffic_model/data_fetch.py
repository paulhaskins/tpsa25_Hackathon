"""SCATS traffic volume data fetching and processing utilities.

Functions:
- download_scats_zip(month: str, year: int, dest_dir: Path) -> Path
- read_scats_zip(zip_path: Path) -> pd.DataFrame
- map_sites_to_nodes(df: pd.DataFrame, site_coords: dict[int, tuple[float,float]], G) -> pd.DataFrame
- load_sample_flow() -> pd.DataFrame  # January 2024 convenience
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple, List
import io
import zipfile

import pandas as pd
import requests
import networkx as nx

from urllib.parse import urljoin
import re

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

# CKAN Action API base for Smart Dublin
CKAN_BASE = "https://data.smartdublin.ie/api/3/action"

# Dataset pages that actually host the SCATS resources
DATASET_PAGES = [
    # 2024
    "https://data.smartdublin.ie/dataset/dcc-scats-detector-volume-jan-jun-2024",
    "https://data.smartdublin.ie/dataset/dcc-scats-detector-volume-jul-dec-2024",
    # 2025
    "https://data.smartdublin.ie/dataset/dcc-scats-detector-volume-jan-jun-2025",
    # older examples (keep a couple as fallbacks)
    "https://data.smartdublin.ie/dataset/dcc-scats-detector-volume-jan-jun-2020",
]
# A tag search page as a last resort
SEARCH_PAGES = [
    "https://data.smartdublin.ie/dataset?tags=detector&tags=volumes",
]

MONTH_ALIASES = {
    "jan": "january", "feb": "february", "mar": "march", "apr": "april",
    "may": "may", "jun": "june", "jul": "july", "aug": "august",
    "sep": "september", "oct": "october", "nov": "november", "dec": "december",
}

def _norm_month_token(m: str) -> list[str]:
    m = m.strip().lower()
    full = MONTH_ALIASES.get(m[:3], m)
    # generate tokens we’ve seen in real links (e.g., scatsapril2024.zip)
    return list({full, full.capitalize(), full[:3], full[:3].capitalize(), full.upper()})

def _abs_url(base: str, href: str) -> str:
    return urljoin(base if base.endswith("/") else base + "/", href)


def ckan_package_show(name_or_id: str) -> dict:
    """Call CKAN package_show for a dataset slug or id and return the result dict.

    Raises RuntimeError if CKAN returns success=false or HTTP errors occur.
    """
    r = requests.get(f"{CKAN_BASE}/package_show", params={"id": name_or_id}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not data.get("success"):
        raise RuntimeError(f"CKAN error: {data}")
    return data["result"]


def list_scats_zip_urls_for_half(year: int, half: str) -> list[str]:
    """Return ZIP resource URLs for a given half-year dataset (jan-jun or jul-dec)."""
    assert half in {"jan-jun", "jul-dec"}
    slug = f"dcc-scats-detector-volume-{half}-{year}"
    pkg = ckan_package_show(slug)
    urls: list[str] = []
    for res in pkg.get("resources", []):
        url = res.get("url") or ""
        fmt = (res.get("format") or "").lower()
        if url.lower().endswith(".zip") or fmt == "zip":
            urls.append(url)
    return urls


def find_scats_zip_links_ckan(month: str, year: int) -> list[str]:
    """Use CKAN to list ZIP resource URLs for the appropriate half, ranked by month match."""
    month_l = month.strip().lower()
    half = "jan-jun" if month_l in {"january", "february", "march", "april", "may", "june"} else "jul-dec"
    urls = list_scats_zip_urls_for_half(year, half)

    def rank(u: str):
        return (0 if month_l in u.lower() else 1, u)

    # Keep only links that mention the target year to avoid cross-year mixes
    urls = [u for u in urls if str(year) in u]
    return sorted(urls, key=rank)

def get_scats_download_links(pages: list[str] | str) -> list[str]:
    """
    Scrape dataset/listing pages for *actual* SCATS ZIP download links.
    We specifically look for anchors whose href contains '/download/' and ends with '.zip'.
    """
    if isinstance(pages, str):
        pages = [pages]
    links: list[str] = []
    for base in pages:
        try:
            resp = requests.get(base, timeout=30)
            resp.raise_for_status()
        except Exception:
            continue
        text = resp.text
        # Find anchors: href=".../download/...something.zip" or just any .zip with scats
        for m in re.finditer(r'href=["\']([^"\']*\.zip)["\']', text, flags=re.IGNORECASE):
            href = m.group(1)
            if not href:
                continue
            url = _abs_url(base, href)
            # sanity filter: looks like scats{month}{year}.zip or similar
            if "scats" in url.lower() and url.lower().endswith(".zip"):
                links.append(url)

    # Dedup preserving order
    seen = set()
    deduped = []
    for u in links:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return deduped


def download_scats_zip(month: str, year: int,
                       dest_dir: Path | str = "data/raw",
                       url: str | None = None) -> Path:
    """
    Download a SCATS monthly ZIP. If 'url' is given, use it directly.
    Otherwise:
      1) scrape the known dataset pages,
      2) rank links by month/year tokens,
      3) try downloading in order until one succeeds.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    if url:
        candidates = [url]
    else:
        # 1) Prefer CKAN resource listing for the correct half-year
        try:
            ckan_urls = find_scats_zip_links_ckan(month, year)
        except Exception:
            ckan_urls = []

        # 2) Fallback to scraping known dataset pages and ranking
        ranked = find_scats_zip_links(DATASET_PAGES, month=month, year=year)
        scraped = ranked or get_scats_download_links(DATASET_PAGES + SEARCH_PAGES)

        # Filter scraped links by year token if possible
        scraped = [u for u in scraped if str(year) in u] or scraped

        # 3) Merge, keeping order (CKAN results first)
        merged: list[str] = []
        seen: set[str] = set()
        for u in [*ckan_urls, *scraped]:
            if u not in seen:
                seen.add(u)
                merged.append(u)
        candidates = merged

        # As an absolute last resort, try a very loose match by year only
        if not candidates and year:
            candidates = [u for u in get_scats_download_links(DATASET_PAGES + SEARCH_PAGES) if str(year) in u]

    # Build a stable local filename to avoid cross-year names from the portal
    safe_month = month.strip().lower()
    stable_name = f"scats_{year}_{safe_month}.zip"
    out_path = dest_dir / stable_name

    # Stream download with simple retries
    last_error: Exception | None = None
    for cand in candidates:
        # Skip obviously wrong links
        if not cand.lower().endswith(".zip"):
            continue
        if str(year) not in cand:
            # enforce year token match to avoid saving 2024 zips for 2019
            continue
        try:
            for attempt in range(3):
                try:
                    with requests.get(cand, timeout=90, stream=True) as r:
                        r.raise_for_status()
                        with open(out_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=1024 * 256):
                                if chunk:
                                    f.write(chunk)
                    # crude ZIP signature check (first two bytes 'PK')
                    head = out_path.read_bytes()[:2]
                    if head != b"PK":
                        raise ValueError("Downloaded file is not a ZIP (no PK header)")
                    return out_path
                except Exception as e:
                    last_error = e
                    if attempt == 2:
                        raise
            
        except Exception as e:
            last_error = e
            continue

    hint = (
        "Could not download a SCATS ZIP automatically. "
        "Try passing a direct resource URL from the dataset page via 'url='."
    )
    if last_error:
        raise RuntimeError(hint) from last_error
    raise RuntimeError(hint)

def read_scats_zip(zip_path: Path | str) -> pd.DataFrame:
    """Read the SCATS CSV inside the ZIP and return a tidy DataFrame.

    Output columns: site_id (int), sum_volume (float), avg_volume (float)
    Index: timestamp (datetime) parsed from 'End Time'.
    """
    zip_path = Path(zip_path)
    with zipfile.ZipFile(zip_path, "r") as zf:
        # Assume single CSV inside; otherwise pick the first .csv
        csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not csv_names:
            raise FileNotFoundError("No CSV found inside ZIP")
        with zf.open(csv_names[0]) as f:
            df = pd.read_csv(f)

    # Standardize column names (strip + lower)
    df.columns = [c.strip() for c in df.columns]
    # Expected columns: 'Site ID', 'End Time', 'Sum volume', 'Avg volume'
    site_col = next((c for c in df.columns if c.lower().replace(" ", "") in {"siteid", "site_id"}), None)
    time_col = next((c for c in df.columns if c.lower().replace(" ", "") in {"endtime", "timestamp"}), None)
    sum_col = next((c for c in df.columns if c.lower().replace(" ", "") in {"sumvolume", "sum_vol", "sum"}), None)
    avg_col = next((c for c in df.columns if c.lower().replace(" ", "") in {"avgvolume", "avg_vol", "avg"}), None)
    if not (site_col and time_col and sum_col and avg_col):
        raise ValueError("CSV missing one of required columns: Site ID, End Time, Sum volume, Avg volume")

    out = pd.DataFrame({
        "site_id": pd.to_numeric(df[site_col], errors="coerce").astype("Int64"),
        "sum_volume": pd.to_numeric(df[sum_col], errors="coerce"),
        "avg_volume": pd.to_numeric(df[avg_col], errors="coerce"),
    })
    ts = pd.to_datetime(df[time_col], errors="coerce", utc=True)
    out.index = ts
    out = out.dropna(subset=["site_id"]).sort_index()
    # ensure site_id int
    out["site_id"] = out["site_id"].astype(int)
    return out


def map_sites_to_nodes(df: pd.DataFrame, site_coords: Dict[int, Tuple[float, float]], G: nx.MultiDiGraph) -> pd.DataFrame:
    """Map SCATS site ids to nearest graph nodes using (lat, lon) coordinates.

    site_coords: dict[site_id] -> (lat, lon)
    Adds a 'node_id' column with the nearest node for each site_id present in df.
    """
    # Prepare node list with coordinates
    nodes = []
    for n, d in G.nodes(data=True):
        x = d.get("x")
        y = d.get("y")
        if x is None or y is None:
            continue
        nodes.append((n, float(y), float(x)))  # (id, lat, lon)
    if not nodes:
        raise ValueError("Graph has no nodes with coordinates 'x' and 'y'")

    # Simple nearest by haversine approximation
    def haversine(lat1, lon1, lat2, lon2):
        from math import radians, sin, cos, asin, sqrt
        R = 6371000.0
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        return 2 * R * asin(sqrt(a))

    site_to_node: Dict[int, int] = {}
    for sid, (slat, slon) in site_coords.items():
        best_node = None
        best_dist = float("inf")
        for n, nlat, nlon in nodes:
            d = haversine(slat, slon, nlat, nlon)
            if d < best_dist:
                best_dist = d
                best_node = n
        if best_node is not None:
            site_to_node[sid] = best_node  # type: ignore[assignment]

    df2 = df.copy()
    df2["node_id"] = df2["site_id"].map(site_to_node)
    return df2


def load_sample_flow(dest_dir: Path | str = "data/raw", url: str | None = None) -> pd.DataFrame:
    """Convenience: download and load January 2024 SCATS volumes as a tidy DataFrame.

    If automatic URL resolution fails on your environment, pass a direct 'url' from the portal,
    or manually download and call read_scats_zip() on the local file.
    """
    zip_path = download_scats_zip("January", 2024, dest_dir=dest_dir, url=url)
    return read_scats_zip(zip_path)




def find_scats_zip_links(pages: List[str] | str, month: Optional[str] = None, year: Optional[int] = None) -> List[str]:
    """Scrape dataset pages and return likely SCATS ZIP links, ranked.

    - Accepts one or more page URLs (dataset pages or listings).
    - Matches anchors like the SmartDublin "Go to resource" buttons:
      <a class="btn btn-md btn-primary" href=".../download/.../scatsjanuary2024.zip">.
    - If month and/or year are provided, prioritize links that contain these tokens.
    """
    links = get_scats_download_links(pages)
    if not links:
        return links
    if month is None and year is None:
        return links
    tokens: List[str] = []
    if year is not None:
        tokens.append(str(year))
    if month:
        tokens.extend([month, month[:3], month.capitalize(), month[:3].capitalize(), month.upper()])
    tokens = [t for t in tokens if t]
    scored: List[tuple[int, str]] = []
    for url in links:
        score = sum(1 for t in tokens if t in url)
        scored.append((score, url))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [u for _, u in scored]


def read_site_coords_csv(path: Path | str,
                         lat_col: str = "lat",
                         lon_col: str = "lon",
                         id_col: str = "site_id") -> Dict[int, Tuple[float, float]]:
    """Read SCATS site coordinates CSV and return mapping id -> (lat, lon).

    The CSV should include site ids and latitude/longitude columns. Common fallbacks
    for columns will be tried if the provided names are not found.
    """
    df = pd.read_csv(path)
    # Resolve columns
    def first(cols: List[str]) -> Optional[str]:
        for c in cols:
            if c in df.columns:
                return c
        return None

    id_c = id_col if id_col in df.columns else first(["site_id", "Site ID", "siteid", "id"])
    lat_c = lat_col if lat_col in df.columns else first(["lat", "latitude", "y"])
    lon_c = lon_col if lon_col in df.columns else first(["lon", "lng", "longitude", "x"])
    if not (id_c and lat_c and lon_c):
        raise ValueError("Site coords CSV must include site_id, lat, lon columns (with common fallbacks)")

    out: Dict[int, Tuple[float, float]] = {}
    for _, row in df.iterrows():
        try:
            sid = int(row[id_c])
            lat = float(row[lat_c])
            lon = float(row[lon_c])
        except Exception:
            continue
        out[sid] = (lat, lon)
    return out

__all__ = [
    "download_scats_zip",
    "read_scats_zip",
    "map_sites_to_nodes",
    "load_sample_flow",
    "get_scats_download_links",
    "find_scats_zip_links",
    "read_site_coords_csv",
]


