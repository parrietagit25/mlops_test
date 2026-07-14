"""Configuración de la UI Streamlit (solo variables de entorno del servidor).

Las URLs internas se usan para HTTP desde el contenedor.
Las URLs públicas se usan solo para enlaces visibles en el navegador.
No se aceptan URLs arbitrarias desde la interfaz.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class UIConfig:
    # Solicitudes HTTP desde Streamlit → Gateway (red Docker o host local).
    api_base_url: str
    # Enlaces para el navegador del usuario.
    api_public_url: str
    openapi_docs_url: str
    phoenix_public_url: str
    connect_timeout_s: float
    read_timeout_s: float
    # Timeout de lectura específico para POST /chat (inferencia local puede ser lenta).
    chat_read_timeout_s: float
    # Timeout de lectura para POST /agents/{skill}/run.
    skill_read_timeout_s: float
    # Timeout para ingest/query RAG (embeddings pueden ser lentos).
    rag_read_timeout_s: float
    # Timeout para crear job de eval (POST rápido) y consultar estado.
    eval_create_timeout_s: float
    eval_read_timeout_s: float
    status_cache_ttl_s: int
    # Zona horaria opcional para timestamps de UI (ej. America/Panama).
    ui_timezone: str


def load_config() -> UIConfig:
    api_public = os.getenv("AILAB_API_PUBLIC_URL", "http://127.0.0.1:8080").rstrip("/")
    phoenix_public = os.getenv(
        "AILAB_PHOENIX_PUBLIC_URL", "http://127.0.0.1:6006"
    ).rstrip("/")
    return UIConfig(
        api_base_url=os.getenv("AILAB_API_BASE_URL", "http://127.0.0.1:8080").rstrip("/"),
        api_public_url=api_public,
        openapi_docs_url=os.getenv("AILAB_OPENAPI_DOCS_URL", f"{api_public}/docs"),
        phoenix_public_url=phoenix_public,
        connect_timeout_s=float(os.getenv("AILAB_HTTP_CONNECT_TIMEOUT", "3")),
        read_timeout_s=float(os.getenv("AILAB_HTTP_READ_TIMEOUT", "15")),
        chat_read_timeout_s=float(os.getenv("AILAB_CHAT_READ_TIMEOUT", "120")),
        skill_read_timeout_s=float(os.getenv("AILAB_SKILL_READ_TIMEOUT", "120")),
        rag_read_timeout_s=float(os.getenv("AILAB_RAG_READ_TIMEOUT", "180")),
        eval_create_timeout_s=float(os.getenv("AILAB_EVAL_CREATE_TIMEOUT", "30")),
        eval_read_timeout_s=float(os.getenv("AILAB_EVAL_READ_TIMEOUT", "15")),
        status_cache_ttl_s=int(os.getenv("AILAB_STATUS_CACHE_TTL", "30")),
        ui_timezone=os.getenv("AILAB_UI_TIMEZONE", "UTC").strip() or "UTC",
    )
