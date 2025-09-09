from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd

from datahub.scats import rank_resources, read_scats_zip


def test_rank_resources_prefers_month_year() -> None:
    resources = [
        {"name": "SCATS Feb 2024", "url": "http://x/abc_feb_2024.zip"},
        {"name": "SCATS Jan 2023", "url": "http://x/abc_jan_2023.zip"},
        {"name": "SCATS 2024", "url": "http://x/abc_2024.zip"},
    ]
    ranked = rank_resources(resources, month="February", year=2024)
    assert ranked[0]["url"].endswith("feb_2024.zip")


def _zip_with_csv(tmp_path: Path, df: pd.DataFrame) -> Path:
    zpath = tmp_path / "scats.zip"
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        with zf.open("data.csv", "w") as f:
            csv = df.to_csv(index=False).encode("utf-8")
            f.write(csv)
    return zpath


def test_read_scats_zip_normalizes_columns(tmp_path) -> None:
    df = pd.DataFrame(
        {
            "Site ID": [1001, 1002],
            "End Time": ["2024-02-01T10:00:00Z", "2024-02-01T11:00:00Z"],
            "Sum volume": [120, 140],
            "Avg volume": [12.0, 14.0],
            "Region": ["Dublin", "Dublin"],
        }
    )
    zpath = _zip_with_csv(tmp_path, df)
    out = read_scats_zip(zpath)
    assert set(["timestamp", "site_id", "sum_volume", "avg_volume"]).issubset(out.columns)
    assert pd.api.types.is_datetime64_any_dtype(out["timestamp"])  # normalized

