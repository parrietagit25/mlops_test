"""Vista Observabilidad (UI-1F) — metadatos Phoenix vía Gateway."""

from __future__ import annotations

import time

import streamlit as st

from api_client import GatewayClient
from components.messages import show_error, show_info, show_warning
from config import UIConfig
from reports_payload import humanize_report_error, parse_observability
from state import OBS_TTL_S, clear_obs_error


def render(client: GatewayClient, cfg: UIConfig) -> None:
    st.markdown("## Observabilidad")
    st.caption(
        "Estado de Arize Phoenix según el FastAPI Gateway. "
        "Streamlit no hace de proxy OTLP ni reenvía trazas."
    )
    show_info(
        "Las trazas se generan en el Gateway hacia Phoenix. "
        "En Chat, `trace_id` puede ser null según la instrumentación."
    )

    if st.button("Actualizar observabilidad", key="obs_refresh"):
        st.session_state.obs_fetched_at = 0.0
        st.rerun()

    now = time.time()
    cached = st.session_state.obs_payload
    fetched_at = float(st.session_state.obs_fetched_at or 0.0)

    if not isinstance(cached, dict) or (now - fetched_at) >= OBS_TTL_S:
        result = client.observability()
        if not result.ok:
            st.session_state.obs_last_error = humanize_report_error(
                error_kind=result.error_kind,
                error_code=result.error_code,
                error_message=result.error_message,
                status_code=result.status_code,
            )
            st.session_state.obs_payload = None
        else:
            parsed, err = parse_observability(result.data)
            if err:
                st.session_state.obs_last_error = err
                st.session_state.obs_payload = None
            else:
                st.session_state.obs_payload = parsed
                st.session_state.obs_fetched_at = now
                clear_obs_error()

    if st.session_state.obs_last_error:
        show_error(st.session_state.obs_last_error)

    data = st.session_state.obs_payload
    if not isinstance(data, dict):
        show_warning("Sin datos de observabilidad. Pulsa actualizar.")
        return

    enabled = data.get("enabled")
    status = data.get("status") or "unavailable"
    st.markdown(f"**Phoenix habilitado:** {'sí' if enabled else 'no'}")
    st.markdown(f"**Estado:** `{status}`")

    url = data.get("url")
    link = url or cfg.phoenix_public_url
    if link and (
        link.startswith("http://127.0.0.1")
        or link.startswith("https://127.0.0.1")
        or link.startswith("http://localhost")
    ):
        st.link_button("Abrir Phoenix UI", link)
    else:
        show_warning("No hay URL pública segura de Phoenix para mostrar.")

    st.caption(
        "Esta vista no consulta Ollama, no lee reports/ y no modifica el tracing."
    )
