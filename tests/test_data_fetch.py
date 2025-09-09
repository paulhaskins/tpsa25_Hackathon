import io
import zipfile
from pathlib import Path
import pandas as pd

from traffic_model import read_scats_zip, get_scats_download_links, find_scats_zip_links

def make_fake_zip(path: Path):
    csv_bytes = io.BytesIO()
    pd.DataFrame({
        "Site ID": [1001, 1001],
        "End Time": ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"],
        "Sum volume": [10, 12],
        "Avg volume": [5, 6],
    }).to_csv(csv_bytes, index=False)
    csv_bytes.seek(0)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("scats.csv", csv_bytes.read())


def test_read_scats_zip(tmp_path: Path):
    zpath = tmp_path / "scats.zip"
    make_fake_zip(zpath)
    df = read_scats_zip(zpath)
    assert list(df.columns) == ["site_id", "sum_volume", "avg_volume"]
    assert df.index.dtype.kind in {"M"}
    assert df.shape[0] == 2


def test_scraper_regex_minimal(monkeypatch):
    # Minimal HTML page containing a SCATS zip link with the expected classes
    html = '''
    <html><body>
      <a class="btn btn-md btn-primary" href="/dataset/.../download/scatsjanuary2024.zip">Go to resource</a>
    </body></html>'''

    class R:
        status_code = 200
        text = html
        
        def raise_for_status(self):
            pass

    def fake_get(url, timeout=30):
        return R()

    import traffic_model.data_fetch
    monkeypatch.setattr(traffic_model.data_fetch.requests, "get", fake_get)

    pages = ["https://data.smartdublin.ie/dataset/dummy"]
    links = get_scats_download_links(pages)
    assert links and links[0].endswith("scatsjanuary2024.zip")

    ranked = find_scats_zip_links(pages, month="January", year=2024)
    assert ranked[0].endswith("scatsjanuary2024.zip")


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q", "-s"]))


