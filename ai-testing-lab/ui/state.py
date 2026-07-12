"""Gestión centralizada de st.session_state (UI-1A / UI-1B)."""

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

# Valor inicial del system prompt (UI-1B). No se muestra en el historial visual.
DEFAULT_SYSTEM_PROMPT = "Eres un asistente útil, preciso y claro."
DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_TOKENS = 512
CHAT_MODELS_TTL_S = 30


def init_session_state() -> None:
    defaults: dict[str, Any] = {
        "page": PAGE_HOME,
        "last_refresh_at": None,
        "lab_status": None,
        "global_error": None,
        "status_fetch_meta": None,
        # UI-1B Chat — historial solo en sesión Streamlit (sin persistencia).
        "chat_messages": [],
        "chat_system_prompt": DEFAULT_SYSTEM_PROMPT,
        "chat_model": None,
        "chat_temperature": DEFAULT_TEMPERATURE,
        "chat_max_tokens": DEFAULT_MAX_TOKENS,
        "chat_request_in_progress": False,
        "chat_last_error": None,
        "chat_models_payload": None,
        "chat_models_fetched_at": 0.0,
        "chat_models_warning": None,
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


def clear_chat() -> None:
    """Elimina solo el historial y el error; conserva modelo/params/system prompt."""
    st.session_state.chat_messages = []
    st.session_state.chat_last_error = None
    st.session_state.chat_request_in_progress = False


def append_chat_message(
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    st.session_state.chat_messages.append(
        {
            "role": role,
            "content": content,
            "metadata": metadata or {},
        }
    )


def invalidate_chat_models_cache() -> None:
    st.session_state.chat_models_payload = None
    st.session_state.chat_models_fetched_at = 0.0
