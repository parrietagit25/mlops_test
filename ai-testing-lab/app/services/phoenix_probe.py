"""Sonda HTTP ligera hacia la UI de Phoenix (URL solo server-side)."""

from __future__ import annotations

import httpx

from core.config import get_settings


def probe_phoenix(timeout: float = 5.0) -> bool:
    settings = get_settings()
    url = settings.phoenix_health_url
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url)
            return resp.status_code < 500
    except Exception:
        return False
