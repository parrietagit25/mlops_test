"""Tarjetas / métricas de estado del laboratorio."""

from __future__ import annotations

from typing import Any

import streamlit as st

STATUS_LABELS = {
    "available": "Disponible",
    "ok": "Disponible",
    "unavailable": "No disponible",
    "disabled": "No disponible",
    "degraded": "Degradado",
    "unknown": "Desconocido",
}


def normalize_status(raw: Any) -> str:
    if raw is None:
        return "unknown"
    text = str(raw).strip().lower()
    if text in {"available", "ok", "healthy", "up"}:
        return "available"
    if text in {"unavailable", "down", "disabled", "offline"}:
        return "unavailable"
    if text in {"degraded", "partial"}:
        return "degraded"
    return "unknown"


def status_badge(label: str, status_key: str) -> str:
    human = STATUS_LABELS.get(status_key, "Desconocido")
    return f"**{label}:** {human}"


def render_component_metrics(components: list[dict[str, Any]] | None) -> None:
    by_name = {str(c.get("name", "")).lower(): c for c in (components or [])}
    cols = st.columns(3)
    mapping = [
        ("Gateway", by_name.get("gateway")),
        ("Ollama", by_name.get("ollama")),
        ("Phoenix", by_name.get("phoenix")),
    ]
    for col, (title, item) in zip(cols, mapping):
        with col:
            raw = (item or {}).get("status") if item else None
            key = normalize_status(raw if item is not None else None)
            st.metric(title, STATUS_LABELS.get(key, "Desconocido"))
