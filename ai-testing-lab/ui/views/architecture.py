"""Vista Arquitectura (UI-1G) — mapa del laboratorio (solo lectura vía Gateway)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from api_client import GatewayClient
from components.messages import show_error, show_info, show_warning
from components.status_cards import STATUS_LABELS, normalize_status
from config import UIConfig

# Diagrama actualizado (Fase 1): Streamlit + evals vía Gateway.
_ARCHITECTURE_MERMAID = """flowchart TD
  Browser[Navegador]
  UI[Streamlit ailab-ui :8501]
  API[FastAPI ailab-api :8080]
  Ollama[Ollama :11434]
  Skills[Agent Runtime / Skills]
  RAG[RAG índice JSON]
  Evals[Job Manager + runners]
  Reports[reports/ vía Gateway]
  Phoenix[Phoenix UI :6006 / OTLP :4317]

  Browser --> UI
  UI -->|HTTP| API
  API --> Ollama
  API --> Skills
  API --> RAG
  API --> Evals
  API --> Reports
  API -->|OTLP| Phoenix
"""


def _component_map(system: dict[str, Any] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    if not system:
        return out
    for item in system.get("components") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").lower()
        if name:
            out[name] = normalize_status(item.get("status"))
    if system.get("gateway") and "gateway" not in out:
        out["gateway"] = normalize_status(system.get("gateway"))
    return out


def _fetch_system(client: GatewayClient) -> tuple[dict[str, Any] | None, str | None]:
    health = client.health()
    system = client.system_status()
    if not health.ok and health.error_kind in {"connection", "timeout", "unavailable"}:
        return None, "Gateway no disponible. El diagrama estático sigue siendo válido."
    if system.ok and isinstance(system.data, dict):
        return system.data, None
    if not system.ok:
        return None, system.error_message or "No se pudo obtener /system/status."
    return None, "Respuesta de /system/status inesperada."


def render(client: GatewayClient, cfg: UIConfig) -> None:
    st.markdown("## Arquitectura")
    st.caption(
        "Mapa del laboratorio en Fase 1 Local. "
        "Streamlit es solo cliente HTTP del FastAPI Gateway."
    )

    show_warning(
        "La imagen de inspiración MLOps en `docs/assets/` es solo estilo visual. "
        "**No** representa la arquitectura real de ai-testing-lab."
    )

    st.markdown("### Flujo real")
    st.code(
        "Navegador → Streamlit (8501) → FastAPI Gateway (8080)\n"
        "         → Ollama / Skills / RAG / Evals / Reports\n"
        "         → Phoenix (trazas OTLP)",
        language="text",
    )

    with st.expander("Diagrama Mermaid (copiar a mermaid.live)", expanded=False):
        st.code(_ARCHITECTURE_MERMAID, language="text")
        st.caption("Fuente conceptual alineada con docs/diagram.md (actualizada a UI + evals vía Gateway).")

    st.markdown("### Capas")
    st.markdown(
        """
| Capa | Rol | Regla |
|---|---|---|
| Streamlit (`ailab-ui`) | UI | Solo HTTP al Gateway |
| FastAPI (`ailab-api`) | Gateway | Único acceso a capacidades internas |
| Ollama | Modelos | Chat + embeddings |
| Skills | Agentes | `summarizer`, `rag_qa` |
| RAG | Retriever | Índice JSON + coseno; sin vector DB |
| Evals | Jobs in-memory | Suites whitelist vía scripts fijos |
| Reports | Artefactos | Lectura solo vía `/reports*` |
| Phoenix | Observabilidad | Trazas; UI no hace proxy OTLP |
"""
    )

    st.markdown("### Servicios Docker (loopback)")
    st.markdown(
        """
| Servicio | Contenedor | Puerto host |
|---|---|---|
| `ui` | `ailab-ui` | `127.0.0.1:8501` |
| `api` | `ailab-api` | `127.0.0.1:8080` |
| `ollama` | `ailab-ollama` | `127.0.0.1:11434` |
| `phoenix` | `ailab-phoenix` | `127.0.0.1:6006` · OTLP `4317` |
"""
    )
    st.caption(
        f"UI interna → API: `{cfg.api_base_url}` · "
        f"Enlaces públicos: API `{cfg.api_public_url}`, Phoenix `{cfg.phoenix_public_url}`."
    )

    st.markdown("### Estado en vivo (Gateway)")
    if st.button("Actualizar estado de arquitectura", key="arch_refresh"):
        st.session_state.arch_system = None
        st.session_state.arch_error = None
        st.rerun()

    if st.session_state.get("arch_system") is None and st.session_state.get("arch_error") is None:
        data, err = _fetch_system(client)
        st.session_state.arch_system = data
        st.session_state.arch_error = err

    if st.session_state.get("arch_error"):
        show_error(str(st.session_state.arch_error))

    cmap = _component_map(st.session_state.get("arch_system"))
    cols = st.columns(3)
    for col, (label, key) in zip(
        cols,
        [("Gateway", "gateway"), ("Ollama", "ollama"), ("Phoenix", "phoenix")],
    ):
        with col:
            status = cmap.get(key, "unknown")
            st.metric(label, STATUS_LABELS.get(status, "Desconocido"))

    if not cmap:
        show_info("Sin telemetría de componentes; el diagrama estático sigue aplicando.")

    st.markdown("### Módulos UI")
    st.markdown(
        """
| Página | Etapa | Consumo Gateway |
|---|---|---|
| Inicio | UI-1A | `/health`, `/system/status`, `/models`, `/rag/status`, `/observability` |
| Chat | UI-1B | `/models`, `/chat` |
| Skills | UI-1C | `/skills`, `/agents/{skill}/run` |
| RAG | UI-1D | `/rag/status`, `/rag/ingest`, `/rag/query` |
| Evaluaciones | UI-1E | `/evals/...` |
| Reportes | UI-1F | `/reports*` |
| Observabilidad | UI-1F | `/observability` |
| Arquitectura | UI-1G | `/system/status` (opcional) |
"""
    )

    st.markdown("### Enlaces seguros")
    c1, c2 = st.columns(2)
    with c1:
        st.link_button("OpenAPI / docs", cfg.openapi_docs_url)
    with c2:
        phoenix = cfg.phoenix_public_url
        if phoenix.startswith("http://127.0.0.1") or phoenix.startswith("http://localhost"):
            st.link_button("Phoenix UI", phoenix)
        else:
            show_warning("URL de Phoenix no es loopback; no se muestra enlace.")

    st.markdown("### Limitaciones Fase 1")
    st.markdown(
        """
- Binds solo en `127.0.0.1` (no exponer a la red).
- Jobs de evaluación **in-memory** (se pierden al reiniciar `ailab-api`).
- Promptfoo / garak **no** instalados en la imagen API (EVAL-RUNTIME-2).
- RAG sin vector database; chat sin streaming ni autenticación.
- Fase 2 multi-cloud: **solo diseño** en `infra/future/` — no implementada.
"""
    )

    st.caption("Documentación: `docs/diagram.md`, `docs/architecture.md`, `CLAUDE.md`.")
