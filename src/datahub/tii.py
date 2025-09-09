from __future__ import annotations

from typing import Dict
import re
from urllib.parse import urlparse
import io

import pandas as pd
import requests


def fetch_tii_portal_metadata(timeout: float = 20.0) -> Dict[str, str]:
    """Fetch minimal metadata from https://data.tii.ie/ homepage.

    This parses anchor links to dataset pages. It is intentionally lightweight
    and can be extended. See TII portal: https://data.tii.ie/
    """
    url = "https://data.tii.ie/"
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "tpsa-traffic/1.0"})
    r.raise_for_status()
    html = r.text
    out: Dict[str, str] = {}
    for m in re.finditer(r'<a[^>]+href=\"(https://data\.tii\.ie/[^\"]+)\"[^>]*>([^<]+)</a>', html, flags=re.I):
        href = m.group(1)
        title = m.group(2).strip()
        out[title] = href
    return out


def load_tii_counts_export(path_or_url: str, timeout: float = 30.0) -> pd.DataFrame:
    """Load a CSV/TSV export of TII Traffic Count data.

    If a URL is provided and direct download works, it is fetched. Otherwise,
    manually export from `https://trafficdata.tii.ie/publicmultinodemap.asp`
    (Export -> CSV or TSV) and pass the local file path here.

    Returns normalized columns: timestamp, station_id, direction (optional),
    class_* (wide), total_volume.
    """
    parsed = urlparse(path_or_url)
    if parsed.scheme in {"http", "https"}:
        r = requests.get(path_or_url, timeout=timeout, headers={"User-Agent": "tpsa-traffic/1.0"})
        r.raise_for_status()
        data = io.BytesIO(r.content)
        sniff = r.headers.get("Content-Type", "text/csv").lower()
        sep = "\t" if "tsv" in sniff else ","
        df = pd.read_csv(data, sep=sep)
    else:
        # local file
        with open(path_or_url, "rb") as f:
            head = f.read(1024)
            sep = "\t" if b"\t" in head else ","
        df = pd.read_csv(path_or_url, sep=sep)

    cols = {c.lower().strip().replace("_", " "): c for c in df.columns}
    def pick(*cands: str) -> str:
        for c in cands:
            if c in cols:
                return cols[c]
        raise KeyError(f"Missing columns among {cands}")

    ts = pick("timestamp", "time", "datetime")
    st = pick("station id", "site id", "station")
    total = pick("total volume", "volume", "count")
    direction = cols.get("direction")

    out = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(df[ts], utc=True, errors="coerce"),
            "station_id": pd.to_numeric(df[st], errors="coerce").astype("Int64"),
            "total_volume": pd.to_numeric(df[total], errors="coerce"),
        }
    )
    if direction:
        out["direction"] = df[direction].astype(str)
    # Copy class columns if any
    for c in df.columns:
        cl = c.lower()
        if cl.startswith("class ") or cl.startswith("class_"):
            out[c] = pd.to_numeric(df[c], errors="coerce")
    return out.dropna(subset=["timestamp", "station_id"]).reset_index(drop=True)


