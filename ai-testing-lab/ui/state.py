"""Gestión mínima de st.session_state para UI-1A."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import streamlit as st

PAGE_HOME = "Inicio"
PAGE_KEYS = (
    "Inicio",
    "Chat",
    "Skills",
    "RAG",
    "Evaluaciones",
    "Reportes",
    "Observabilidad",
    "Arquitectura",
)


def init_session_state() -> None:
    defaults: dict[str, Any] = {
        "page": PAGE_HOME,
        "last_refresh_at": None,
        "lab_status": None,
        "global_error": None,
        "status_fetch_meta": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def set_page(page: str) -> None:
    """Actualiza la página activa (también gestiona el radio con key='page')."""
    if page in PAGE_KEYS:
        st.session_state.page = page


def mark_refreshed() -> None:
    st.session_state.last_refresh_at = datetime.now(tz=timezone.utc).isoformat()


def set_lab_status(payload: dict[str, Any] | None, meta: dict[str, Any] | None = None) -> None:
    st.session_state.lab_status = payload
    st.session_state.status_fetch_meta = meta
    mark_refreshed()


def set_global_error(message: str | None) -> None:
    st.session_state.global_error = message
