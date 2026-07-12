"""Gestión centralizada de st.session_state (UI-1A … UI-1D)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import streamlit as st

from rag_payload import HISTORY_LIMIT as RAG_HISTORY_LIMIT
from rag_payload import QUERY_TOP_K_DEFAULT
from skills_payload import (
    RAG_TOP_K_DEFAULT,
    SKILLS_HISTORY_LIMIT,
    SUMMARIZER_MAX_SENTENCES_DEFAULT,
    summarize_input,
    truncate_output,
)

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
SKILLS_LIST_TTL_S = 30
RAG_STATUS_TTL_S = 30


def format_ui_timestamp(tz_name: str = "UTC") -> str:
    """Timestamp local de UI con zona configurada (fallback UTC)."""
    try:
        tz = ZoneInfo(tz_name) if tz_name else ZoneInfo("UTC")
        label = tz_name or "UTC"
    except ZoneInfoNotFoundError:
        tz = timezone.utc
        label = "UTC"
    return datetime.now(tz=tz).isoformat(timespec="seconds") + f" ({label})"


def init_session_state() -> None:
    defaults: dict[str, Any] = {
        "page": PAGE_HOME,
        "last_refresh_at": None,
        "lab_status": None,
        "global_error": None,
        "status_fetch_meta": None,
        # UI-1B Chat
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
        # UI-1C Skills
        "skills_list": None,
        "skills_list_fetched_at": 0.0,
        "skills_selected": None,
        "skills_request_in_progress": False,
        "skills_last_error": None,
        "skills_last_result": None,
        "skills_history": [],
        "skills_summarizer_text": "",
        "skills_summarizer_max_sentences": SUMMARIZER_MAX_SENTENCES_DEFAULT,
        "skills_rag_question": "",
        "skills_rag_top_k": RAG_TOP_K_DEFAULT,
        # UI-1D RAG
        "rag_status_payload": None,
        "rag_status_fetched_at": 0.0,
        "rag_ingest_in_progress": False,
        "rag_query_in_progress": False,
        "rag_last_error": None,
        "rag_last_ingest_result": None,
        "rag_last_query_result": None,
        "rag_query_history": [],
        "rag_question": "",
        "rag_top_k": QUERY_TOP_K_DEFAULT,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def set_page(page: str) -> None:
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


def invalidate_skills_cache() -> None:
    st.session_state.skills_list = None
    st.session_state.skills_list_fetched_at = 0.0


def clear_skills_history() -> None:
    st.session_state.skills_history = []
    st.session_state.skills_last_error = None
    st.session_state.skills_last_result = None
    st.session_state.skills_request_in_progress = False


def append_skills_history_entry(entry: dict[str, Any]) -> None:
    history = list(st.session_state.skills_history or [])
    history.insert(0, entry)
    st.session_state.skills_history = history[:SKILLS_HISTORY_LIMIT]


def build_skills_history_entry(
    *,
    skill: str,
    payload: dict[str, Any],
    status: str,
    output: str | None = None,
    metadata: dict[str, Any] | None = None,
    error: str | None = None,
    duration_ms: float | None = None,
) -> dict[str, Any]:
    return {
        "skill": skill,
        "executed_at": format_ui_timestamp(),
        "input_summary": summarize_input(skill, payload),
        "output": truncate_output(output or "") if output else None,
        "metadata": metadata or {},
        "status": status,
        "error": error,
        "duration_ms": duration_ms,
    }


def invalidate_rag_status_cache() -> None:
    st.session_state.rag_status_payload = None
    st.session_state.rag_status_fetched_at = 0.0


def clear_rag_history() -> None:
    """Solo historial/resultados RAG; no toca Chat ni Skills."""
    st.session_state.rag_query_history = []
    st.session_state.rag_last_error = None
    st.session_state.rag_last_query_result = None
    st.session_state.rag_last_ingest_result = None
    st.session_state.rag_ingest_in_progress = False
    st.session_state.rag_query_in_progress = False


def append_rag_history_entry(entry: dict[str, Any]) -> None:
    history = list(st.session_state.rag_query_history or [])
    history.insert(0, entry)
    st.session_state.rag_query_history = history[:RAG_HISTORY_LIMIT]
