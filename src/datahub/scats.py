from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import requests

from .ckan_client import CKANClient, list_resource_downloads
from .cache import get_cached, put_cached


SMART_DUBLIN_API = "https://data.smartdublin.ie/api/3/action"


def _month_aliases() -> Dict[str, str]:
    return {
        "jan": "january",
        "feb": "february",
        "mar": "march",
        "apr": "april",
        "may": "may",
        "jun": "june",
        "jul": "july",
        "aug": "august",
        "sep": "september",
        "oct": "october",
        "nov": "november",
        "dec": "december",
    }


def discover_scats_resources(slugs: List[str], timeout: float = 20.0, retries: int = 3) -> List[Dict]:
    """Discover SCATS resource ZIPs via CKAN and fallback HTML parsing.

    Dataset page: https://data.smartdublin.ie/dataset/{slug}
    """
    client = CKANClient(SMART_DUBLIN_API, timeout=timeout, retries=retries)
    results: List[Dict] = []
    for slug in slugs:
        try:
            pkg = client.package_show(slug)
            resources = list_resource_downloads(pkg, only_zip=True)
            for r in resources:
                url = r.get("url", "").lower()
                if url.endswith(".zip") and "scats" in url:
                    r2 = dict(r)
                    r2["slug"] = slug
                    results.append(r2)
        except Exception:
            pass
        # HTML fallback
        try:
            page_url = f"https://data.smartdublin.ie/dataset/{slug}"
            html = requests.get(page_url, timeout=timeout, headers={"User-Agent": "tpsa-traffic/1.0"}).text
            for m in re.finditer(r'href=\"([^\"]+/download/[^\"]+\.zip)\"', html, flags=re.I):
                url = m.group(1)
                results.append({"slug": slug, "name": url.split("/")[-1], "format": "ZIP", "url": url})
        except Exception:
            continue
    # de-duplicate by url
    dedup: Dict[str, Dict] = {}
    for r in results:
        dedup[r["url"]] = r
    return list(dedup.values())


def _score_resource(res: Dict, month: Optional[str], year: Optional[int]) -> int:
    score = 0
    name = (res.get("name") or "") + " " + (res.get("url") or "")
    name = name.lower()
    if year is not None and str(year) in name:
        score += 10
    if month:
        m = month.lower()
        m_full = _month_aliases().get(m[:3], m)
        if m_full in name:
            score += 10
        if m[:3] in name:
            score += 5
    return score


def rank_resources(resources: List[Dict], month: Optional[str], year: Optional[int]) -> List[Dict]:
    return sorted(resources, key=lambda r: _score_resource(r, month, year), reverse=True)


def download_zip(url: str, dest_dir: Path, timeout: float = 30.0) -> Path:
    cached = get_cached(url)
    if cached:
        return cached
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = url.split("/")[-1]
    out = dest_dir / filename
    with requests.get(url, stream=True, timeout=timeout, headers={"User-Agent": "tpsa-traffic/1.0"}) as r:
        r.raise_for_status()
        with open(out, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    # validate ZIP header
    header = out.read_bytes()[:4]
    if header != b"PK\x03\x04":
        out.unlink(missing_ok=True)
        raise ValueError("Downloaded file is not a ZIP: invalid header")
    put_cached(url, out)
    return out


def _normalize_columns(cols: List[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for c in cols:
        lc = c.strip().lower().replace("_", " ")
        mapping[c] = lc
    return mapping


def read_scats_zip(zip_path: Path) -> pd.DataFrame:
    """Read first CSV from a SCATS ZIP and normalize columns.

    Expected columns (case/space tolerant):
    - Site ID -> site_id
    - End Time -> timestamp (UTC)
    - Sum volume -> sum_volume
    - Avg volume -> avg_volume
    Optional: Region -> region
    """
    with zipfile.ZipFile(zip_path, "r") as zf:
        csv_name = next((n for n in zf.namelist() if n.lower().endswith(".csv")), None)
        if not csv_name:
            raise ValueError("No CSV found in ZIP")
        data = zf.read(csv_name)
    df = pd.read_csv(io.BytesIO(data))
    norm = _normalize_columns(list(df.columns))
    df = df.rename(columns={k: v for k, v in norm.items()})

    def pick(*cands: str) -> str:
        for c in cands:
            if c in df.columns:
                return c
        raise KeyError(f"Missing columns among {cands}")

    site_col = pick("site id", "site", "detector site id")
    time_col = pick("end time", "time", "timestamp")
    sum_col = pick("sum volume", "sum", "volume")
    avg_col = pick("avg volume", "avg", "average volume")
    region_col = "region" if "region" in df.columns else None

    out = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(df[time_col], utc=True, errors="coerce"),
            "site_id": pd.to_numeric(df[site_col], errors="coerce").astype("Int64"),
            "sum_volume": pd.to_numeric(df[sum_col], errors="coerce"),
            "avg_volume": pd.to_numeric(df[avg_col], errors="coerce"),
        }
    )
    if region_col:
        out["region"] = df[region_col].astype(str)
    out = out.dropna(subset=["timestamp", "site_id"]).reset_index(drop=True)
    return out


def load_month(month: str, year: int, dest_dir: str | Path = "data/raw", timeout: float = 20.0, retries: int = 3) -> pd.DataFrame:
    slugs = [
        "dcc-scats-detector-volume-jan-jun-2024",
        "dcc-scats-detector-volume-jul-dec-2024",
        "dcc-scats-detector-volume-jan-jun-2025",
    ]
    resources = discover_scats_resources(slugs, timeout=timeout, retries=retries)
    if not resources:
        raise RuntimeError("No SCATS resources discovered; try `datahub scats list`.")
    ranked = rank_resources(resources, month=month, year=year)
    if not ranked:
        raise RuntimeError("No matching SCATS resource after ranking.")
    # pick best; if score zero but same year resources exist, allow fallback
    best = ranked[0]
    if str(year) not in (best.get("name", "") + " " + best.get("url", "")):
        year_alts = [r for r in resources if str(year) in (r.get("name", "") + " " + r.get("url", ""))]
        if year_alts:
            best = year_alts[0]
        else:
            raise RuntimeError(f"No SCATS resources found for year {year}.")
    zip_path = download_zip(best["url"], Path(dest_dir))
    return read_scats_zip(zip_path)


def unpack_all_scats_archives(scats_dir: Path = Path("data/raw/scats"), 
                             output_dir: Path = Path("data/processed")) -> pd.DataFrame:
    """Unpack and merge all SCATS zip files under data/raw/scats/ (multiple years)."""
    scats_dir = Path(scats_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    all_dataframes = []
    processed_files = []
    
    # Find all SCATS zip files
    zip_files = list(scats_dir.rglob("*.zip"))
    print(f"Found {len(zip_files)} SCATS zip files")
    
    for zip_path in zip_files:
        try:
            print(f"Processing {zip_path.name}...")
            df = read_scats_zip(zip_path)
            
            # Add metadata
            df["source_file"] = zip_path.name
            df["source_year"] = _extract_year_from_filename(zip_path.name)
            df["source_month"] = _extract_month_from_filename(zip_path.name)
            
            all_dataframes.append(df)
            processed_files.append(zip_path.name)
            
        except Exception as e:
            print(f"Error processing {zip_path.name}: {e}")
            continue
    
    if not all_dataframes:
        raise RuntimeError("No SCATS data could be processed")
    
    # Concatenate all data
    print("Concatenating all SCATS data...")
    combined_df = pd.concat(all_dataframes, ignore_index=True)
    
    # Standardize columns
    combined_df = _standardize_scats_columns(combined_df)
    
    # Convert End_Time to datetime
    combined_df["End_Time"] = pd.to_datetime(combined_df["End_Time"], errors="coerce")
    
    # Remove rows with invalid timestamps
    combined_df = combined_df.dropna(subset=["End_Time"])
    
    print(f"Combined dataset: {len(combined_df)} rows from {len(processed_files)} files")
    print(f"Date range: {combined_df['End_Time'].min()} to {combined_df['End_Time'].max()}")
    
    # Save combined data
    output_file = output_dir / "scats_combined_data.csv"
    combined_df.to_csv(output_file, index=False)
    print(f"Saved combined SCATS data to {output_file}")
    
    return combined_df


def _extract_year_from_filename(filename: str) -> int:
    """Extract year from SCATS filename."""
    import re
    # Look for 4-digit year
    year_match = re.search(r'20\d{2}', filename)
    if year_match:
        return int(year_match.group())
    return 2020  # Default fallback


def _extract_month_from_filename(filename: str) -> str:
    """Extract month from SCATS filename."""
    import re
    month_patterns = {
        r'jan': 'january', r'feb': 'february', r'mar': 'march', r'apr': 'april',
        r'may': 'may', r'jun': 'june', r'jul': 'july', r'aug': 'august',
        r'sep': 'september', r'oct': 'october', r'nov': 'november', r'dec': 'december'
    }
    
    filename_lower = filename.lower()
    for pattern, month in month_patterns.items():
        if re.search(pattern, filename_lower):
            return month
    return 'unknown'


def _standardize_scats_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize SCATS column names."""
    column_mapping = {
        'timestamp': 'End_Time',
        'site_id': 'Site',
        'sum_volume': 'Sum_Volume',
        'avg_volume': 'Avg_Volume',
        'region': 'Region'
    }
    
    # Rename columns if they exist
    for old_col, new_col in column_mapping.items():
        if old_col in df.columns:
            df = df.rename(columns={old_col: new_col})
    
    # Ensure required columns exist
    required_cols = ['End_Time', 'Site', 'Sum_Volume', 'Avg_Volume']
    for col in required_cols:
        if col not in df.columns:
            if col == 'Sum_Volume' and 'Avg_Volume' in df.columns:
                # Estimate sum from average (assuming 1-hour intervals)
                df[col] = df['Avg_Volume']
            elif col == 'Avg_Volume' and 'Sum_Volume' in df.columns:
                # Use sum as average
                df[col] = df['Sum_Volume']
            else:
                df[col] = 0  # Fill with zeros
    
    return df


def aggregate_scats_demand_profiles(combined_df: pd.DataFrame, 
                                  output_dir: Path = Path("data/processed")) -> pd.DataFrame:
    """Aggregate SCATS data to create average hourly demand profiles per site."""
    output_dir = Path(output_dir)
    
    # Extract hour from timestamp
    combined_df["hour"] = combined_df["End_Time"].dt.hour
    
    # Group by Site and hour, calculate average daily profile
    demand_profiles = combined_df.groupby(["Site", "hour"]).agg({
        "Sum_Volume": "mean",
        "Avg_Volume": "mean",
        "Region": "first"
    }).reset_index()
    
    # Round to integers
    demand_profiles["Sum_Volume"] = demand_profiles["Sum_Volume"].round().astype(int)
    demand_profiles["Avg_Volume"] = demand_profiles["Avg_Volume"].round().astype(int)
    
    # Save demand profiles
    output_file = output_dir / "scats_demand_profiles.csv"
    demand_profiles.to_csv(output_file, index=False)
    print(f"Saved demand profiles to {output_file}")
    
    return demand_profiles


def load_scats_profiles(profiles_file: Path = Path("data/processed/scats_demand_profiles.csv")) -> pd.DataFrame:
    """Return average hourly demand profiles per SCATS site."""
    profiles_file = Path(profiles_file)
    
    if not profiles_file.exists():
        raise FileNotFoundError(f"SCATS profiles file not found: {profiles_file}")
    
    return pd.read_csv(profiles_file)


def process_all_scats_data(scats_dir: Path = Path("data/raw/scats"), 
                          output_dir: Path = Path("data/processed")) -> pd.DataFrame:
    """Complete SCATS processing pipeline: unpack, merge, and aggregate."""
    print("Starting SCATS data processing pipeline...")
    
    # Step 1: Unpack and merge all archives
    combined_df = unpack_all_scats_archives(scats_dir, output_dir)
    
    # Step 2: Aggregate to demand profiles
    demand_profiles = aggregate_scats_demand_profiles(combined_df, output_dir)
    
    print("SCATS processing pipeline completed successfully!")
    return demand_profiles


