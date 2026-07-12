"""Punto de entrada Streamlit — ai-testing-lab UI (UI-1A / UI-1A.1).

Arquitectura:
  Navegador → Streamlit → FastAPI Gateway → (Ollama / skills / RAG / evals / …)

La UI nunca importa módulos de `app/` ni ejecuta scripts.

UI-1A.1: las vistas viven en `views/` (no en `pages/`) para evitar la
navegación multipágina automática de Streamlit.
UI-1B: Chat funcional vía POST /chat (sin acceso directo a Ollama).
UI-1C: Skills vía GET /skills y POST /agents/{skill}/run.
UI-1D: RAG vía /rag/status, /rag/ingest y /rag/query.
"""

from __future__ import annotations

import streamlit as st

from api_client import GatewayClient
from components.header import render_header
from components.navigation import render_sidebar
from config import load_config
from state import init_session_state
from views import architecture, chat, evaluations, home, observability, rag, reports, skills

st.set_page_config(
    page_title="ai-testing-lab",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS mínimo: contraste tema + indicador de navegación.
st.markdown(
    """
    <style>
      .block-container { max-width: 1100px; padding-top: 1.2rem; }
      .ailab-header { margin-bottom: 1rem; }
      .ailab-title {
        font-size: 1.75rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        color: var(--text-color);
      }
      .ailab-subtitle {
        color: var(--text-color);
        opacity: 0.78;
        font-size: 0.95rem;
        margin-top: 0.15rem;
      }
      .ailab-nav-active {
        margin-top: 0.55rem;
        padding: 0.4rem 0.55rem;
        border-radius: 0.35rem;
        background: rgba(61, 139, 253, 0.16);
        border: 1px solid rgba(61, 139, 253, 0.45);
        color: var(--text-color);
        font-size: 0.85rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

init_session_state()
cfg = load_config()
client = GatewayClient(cfg)

render_header()
page = render_sidebar()

ROUTES = {
    "Inicio": lambda: home.render_home(client, cfg),
    "Chat": lambda: chat.render(client, cfg),
    "Skills": lambda: skills.render(client, cfg),
    "RAG": lambda: rag.render(client, cfg),
    "Evaluaciones": evaluations.render,
    "Reportes": reports.render,
    "Observabilidad": observability.render,
    "Arquitectura": architecture.render,
}

ROUTES.get(page, ROUTES["Inicio"])()
