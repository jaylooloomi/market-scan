"""Shared HTTP session with sane timeouts, retries, and a polite User-Agent."""
from __future__ import annotations

from functools import lru_cache

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from polydig_mcp.common.errors import SensorError
from polydig_mcp.common.settings import get_settings


@lru_cache(maxsize=1)
def get_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=2,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.headers.update({"User-Agent": get_settings().user_agent})
    return s


def polite_get(url: str, *, params: dict | None = None, timeout: float | None = None) -> requests.Response:
    """GET with shared session; raises SensorError("fetch_failed") on any network error."""
    settings = get_settings()
    try:
        resp = get_session().get(url, params=params, timeout=timeout or settings.http_timeout)
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:
        raise SensorError("fetch_failed", f"GET {url} failed: {e}") from e
