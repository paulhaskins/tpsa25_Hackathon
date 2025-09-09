from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone


INDEX_PATH = Path("data/raw/_cache_index.json")


def _read_index() -> dict:
    if INDEX_PATH.exists():
        try:
            return json.loads(INDEX_PATH.read_text("utf-8"))
        except Exception:
            return {}
    return {}


def _write_index(idx: dict) -> None:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(idx, indent=2), encoding="utf-8")


def get_cached(url: str) -> Optional[Path]:
    idx = _read_index()
    meta = idx.get(url)
    if not meta:
        return None
    p = Path(meta.get("path", ""))
    if p.exists():
        return p
    return None


def put_cached(url: str, path: Path) -> None:
    idx = _read_index()
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    idx[url] = {
        "path": str(path),
        "sha256": sha,
        "size": len(data),
        "created": datetime.now(timezone.utc).isoformat(),
    }
    _write_index(idx)


