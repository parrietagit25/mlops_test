"""Sonda HTTP ligera hacia Ollama (sin shell)."""

from __future__ import annotations

from typing import Any

import httpx

from core.config import get_settings


class OllamaUnavailableError(RuntimeError):
    pass


def probe_ollama(timeout: float = 5.0) -> bool:
    settings = get_settings()
    url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
            return resp.status_code == 200
    except Exception:
        return False


def list_ollama_tags(timeout: float = 10.0) -> list[dict[str, Any]]:
    settings = get_settings()
    url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                raise OllamaUnavailableError(
                    f"Ollama respondió HTTP {resp.status_code} en /api/tags."
                )
            data = resp.json()
            return list(data.get("models") or [])
    except OllamaUnavailableError:
        raise
    except Exception as exc:
        raise OllamaUnavailableError(f"Ollama no disponible: {exc}") from exc
