from __future__ import annotations

import time
from typing import Any, List, Dict

import requests


class CKANClient:
    """Tiny CKAN Action API client.

    Docs: https://docs.ckan.org/en/2.9/api/
    """

    def __init__(
        self,
        base_api: str,
        timeout: float = 20.0,
        retries: int = 3,
        user_agent: str = "tpsa-traffic/1.0",
    ) -> None:
        self.base_api = base_api.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.headers = {"User-Agent": user_agent}

    def _action(self, name: str, **params: Any) -> dict:
        url = f"{self.base_api}/{name}"
        last: Exception | None = None
        backoff = 1.0
        for _ in range(max(1, self.retries)):
            try:
                r = requests.get(url, params=params, headers=self.headers, timeout=self.timeout)
                r.raise_for_status()
                data = r.json()
                if not data.get("success"):
                    raise RuntimeError(f"CKAN action failed: {data}")
                return data["result"]
            except Exception as e:  # pragma: no cover - exercised via mocks
                last = e
                time.sleep(backoff)
                backoff *= 2
        raise RuntimeError(f"CKAN request failed after retries: {url}") from last

    def package_show(self, dataset_slug: str) -> dict:
        return self._action("package_show", id=dataset_slug)


def list_resource_downloads(pkg: dict, only_zip: bool = True) -> List[Dict]:
    out: List[Dict] = []
    for res in pkg.get("resources", []):
        url = (res.get("url") or "").strip()
        fmt = (res.get("format") or "").strip().upper()
        if not url:
            continue
        if only_zip and not url.lower().endswith(".zip"):
            continue
        out.append(
            {
                "name": res.get("name"),
                "format": fmt,
                "url": url,
                "id": res.get("id"),
                "created": res.get("created"),
                "mimetype": res.get("mimetype"),
            }
        )
    return out


