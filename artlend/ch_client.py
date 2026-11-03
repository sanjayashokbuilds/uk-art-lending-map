"""Small Companies House API client with throttling and an on-disk cache.

Companies House allows 600 requests per 5 minutes per key, so we keep to
about 2 requests a second and back off on HTTP 429. Every JSON response is
cached under .cache/ so a rerun costs nothing.
"""

import hashlib
import json
import os
import time
from pathlib import Path

import requests

API = "https://api.company-information.service.gov.uk"
CACHE = Path(".cache")
MIN_GAP = 0.55  # seconds between live requests


class CHClient:
    def __init__(self, api_key=None, cache_dir=CACHE):
        self.key = api_key or os.environ.get("CH_API_KEY")
        if not self.key:
            raise SystemExit("Set CH_API_KEY to your Companies House API key.")
        self.session = requests.Session()
        self.session.auth = (self.key, "")
        self.cache = Path(cache_dir)
        self.cache.mkdir(exist_ok=True)
        self._last = 0.0

    def _wait(self):
        gap = time.time() - self._last
        if gap < MIN_GAP:
            time.sleep(MIN_GAP - gap)
        self._last = time.time()

    def _cache_path(self, url, params):
        raw = url + json.dumps(params or {}, sort_keys=True)
        return self.cache / (hashlib.sha1(raw.encode()).hexdigest() + ".json")

    def get(self, path, params=None):
        """GET a JSON endpoint. Returns None on 404."""
        url = path if path.startswith("http") else API + path
        cp = self._cache_path(url, params)
        if cp.exists():
            return json.loads(cp.read_text())
        for attempt in range(5):
            self._wait()
            r = self.session.get(url, params=params, timeout=30)
            if r.status_code == 429:
                time.sleep(30 * (attempt + 1))
                continue
            if r.status_code == 404:
                cp.write_text("null")
                return None
            r.raise_for_status()
            data = r.json()
            cp.write_text(json.dumps(data))
            return data
        raise RuntimeError(f"Rate limited too many times: {url}")

    def get_all(self, path, key="items", page_size=100, params=None):
        """Page through a list endpoint."""
        out, start = [], 0
        while True:
            p = dict(params or {}, items_per_page=page_size, start_index=start)
            data = self.get(path, p)
            if not data:
                break
            items = data.get(key) or []
            out.extend(items)
            total = data.get("total_count") or data.get("total_results") or 0
            start += page_size
            if not items or start >= total:
                break
        return out

    def download_pdf(self, document_metadata_url, dest):
        """Download a filed document (e.g. a charge deed) as PDF."""
        dest = Path(dest)
        if dest.exists() and dest.stat().st_size > 0:
            return dest
        for attempt in range(5):
            self._wait()
            r = self.session.get(
                document_metadata_url.rstrip("/") + "/content",
                headers={"Accept": "application/pdf"},
                timeout=60,
                allow_redirects=True,  # requests drops auth on the S3 redirect
            )
            if r.status_code == 429:
                time.sleep(30 * (attempt + 1))
                continue
            if r.status_code in (404, 406):
                return None
            r.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(r.content)
            return dest
        return None
