"""Navegación lateral única (personalizada)."""

from __future__ import annotations

import streamlit as st

from state import PAGE_KEYS, PAGE_HOME

# Etapas futuras — solo informativo; sin botones operativos.
_PENDING_STAGE = {
    "Skills": "UI-1C",
    "RAG": "UI-1D",
    "Evaluaciones": "UI-1E",
    "Reportes": "UI-1F",
    "Observabilidad": "UI-1F",
    "Arquitectura": "UI-1G",
}


def render_sidebar() -> str:
    st.sidebar.markdown("### Navegación")

    # `key="page"` sincroniza la opción activa con session_state en cada rerun.
    if "page" not in st.session_state or st.session_state.page not in PAGE_KEYS:
        st.session_state.page = PAGE_HOME

    st.sidebar.radio(
        "Secciones",
        options=list(PAGE_KEYS),
        key="page",
        label_visibility="collapsed",
    )

    active = st.session_state.page
    st.sidebar.markdown(
        f'<div class="ailab-nav-active">Activa: <strong>{active}</strong></div>',
        unsafe_allow_html=True,
    )

    pending = _PENDING_STAGE.get(active)
    if pending:
        st.sidebar.caption(f"Módulo pendiente · se implementará en **{pending}**.")
    elif active == "Chat":
        st.sidebar.caption("Módulo operativo (UI-1B · Chat).")
    else:
        st.sidebar.caption("Módulo operativo (UI-1A).")

    return active
