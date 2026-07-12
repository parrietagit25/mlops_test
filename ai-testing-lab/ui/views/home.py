"""Página Inicio — estado del laboratorio vía Gateway."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import streamlit as st

from api_client import ApiResult, GatewayClient
from components.messages import show_error, show_info, show_warning
from components.status_cards import normalize_status, render_component_metrics
from config import UIConfig
from state import set_global_error, set_lab_status


def _component_status(system: dict[str, Any] | None, name: str) -> str:
    if not system:
        return "unknown"
    for item in system.get("components") or []:
        if str(item.get("name", "")).lower() == name.lower():
            return normalize_status(item.get("status"))
    if name.lower() == "gateway" and system.get("gateway"):
        return normalize_status(system.get("gateway"))
    return "unknown"


def _fetch_bundle(client: GatewayClient) -> dict[str, Any]:
    """Consulta endpoints de estado. No bloquea el proceso ante fallos parciales."""
    health = client.health()
    system = client.system_status()
    models = client.models()
    rag = client.rag_status()
    obs = client.observability()

    gateway_down = (not health.ok) and health.error_kind in {
        "connection",
        "timeout",
        "server_error",
        "unavailable",
    }

    return {
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
        "gateway_reachable": health.ok,
        "gateway_down": gateway_down,
        "health": health,
        "system": system,
        "models": models,
        "rag": rag,
        "observability": obs,
    }


def _result_data(result: ApiResult) -> dict[str, Any] | None:
    if result.ok and isinstance(result.data, dict):
        return result.data
    return None


def render_home(client: GatewayClient, cfg: UIConfig) -> None:
    st.markdown("## Estado del laboratorio")
    st.caption(
        "Datos obtenidos exclusivamente del FastAPI Gateway. "
        "TTL de caché de estado: "
        f"{cfg.status_cache_ttl_s}s (el botón limpia la caché)."
    )

    col_a, col_b = st.columns([1, 3])
    with col_a:
        refresh = st.button("Actualizar estado", type="primary", use_container_width=True)
    with col_b:
        last = st.session_state.get("last_refresh_at")
        if last:
            st.caption(f"Última actualización visual: `{last}`")

    if refresh or st.session_state.get("lab_status") is None:
        # Invalidar caché lógica: siempre refetch al pulsar o en primera carga.
        bundle = _fetch_bundle(client)
        set_lab_status(bundle, meta={"source": "gateway"})
        if bundle["gateway_down"]:
            set_global_error("Gateway no disponible")
        else:
            set_global_error(None)

    bundle: dict[str, Any] = st.session_state.get("lab_status") or {}
    health: ApiResult = bundle.get("health")  # type: ignore[assignment]
    system_r: ApiResult = bundle.get("system")  # type: ignore[assignment]
    models_r: ApiResult = bundle.get("models")  # type: ignore[assignment]
    rag_r: ApiResult = bundle.get("rag")  # type: ignore[assignment]
    obs_r: ApiResult = bundle.get("observability")  # type: ignore[assignment]

    if bundle.get("gateway_down"):
        show_error(
            "Gateway no disponible. Comprueba que `ailab-api` esté en ejecución "
            "y pulsa **Actualizar estado**."
        )
        if health and health.error_message:
            st.caption(health.error_message)
        return

    if st.session_state.get("global_error"):
        show_warning(st.session_state.global_error)

    system = _result_data(system_r) if system_r else None
    models = _result_data(models_r) if models_r else None
    rag = _result_data(rag_r) if rag_r else None
    obs = _result_data(obs_r) if obs_r else None

    # Componentes
    if system:
        render_component_metrics(system.get("components"))
    else:
        show_warning(
            "No se pudo obtener `/system/status`. "
            + (system_r.error_message if system_r and system_r.error_message else "")
        )
        # Health parcial: al menos el gateway responde.
        if health and health.ok:
            st.metric("Gateway", "Disponible")

    st.divider()
    st.markdown("### Modelos")
    m1, m2, m3 = st.columns(3)
    chat_model = (system or {}).get("chat_model") if system else None
    embed_model = (system or {}).get("embedding_model") if system else None
    if not chat_model and models:
        for item in models.get("chat_models") or []:
            if item.get("default"):
                chat_model = item.get("name")
                break
    if not embed_model and models:
        for item in models.get("embedding_models") or []:
            if item.get("default"):
                embed_model = item.get("name")
                break
    with m1:
        st.metric("Chat por defecto", chat_model or "—")
    with m2:
        st.metric("Embeddings", embed_model or "—")
    with m3:
        ollama_models = normalize_status((models or {}).get("ollama_status")) if models else "unknown"
        from components.status_cards import STATUS_LABELS

        st.metric("Ollama (modelos)", STATUS_LABELS.get(ollama_models, "Desconocido"))

    if models_r and not models_r.ok:
        show_info(f"Modelos: {models_r.error_message}")

    st.divider()
    st.markdown("### RAG")
    if rag:
        r1, r2, r3 = st.columns(3)
        with r1:
            st.metric("Índice", "Disponible" if rag.get("available") else "No disponible")
        with r2:
            st.metric("Documentos", rag.get("documents_indexed", "—"))
        with r3:
            st.metric("Fragmentos", rag.get("chunks_indexed", "—"))
        if rag.get("warning"):
            st.caption(str(rag["warning"]))
    elif rag_r and not rag_r.ok:
        show_warning(f"RAG: {rag_r.error_message}")
    else:
        show_info("Sin datos de RAG.")

    st.divider()
    st.markdown("### Actividad reciente")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Última evaluación**")
        last_eval = (system or {}).get("last_evaluation") if system else None
        if last_eval:
            st.write(
                f"- Job: `{last_eval.get('job_id', '—')}`\n"
                f"- Suite: `{last_eval.get('suite', '—')}`\n"
                f"- Estado: `{last_eval.get('status', '—')}`"
            )
        else:
            st.caption("Sin evaluaciones registradas en el proceso actual del Gateway.")
    with c2:
        st.markdown("**Último reporte**")
        last_rep = (system or {}).get("last_report") if system else None
        if last_rep:
            st.write(
                f"- ID: `{last_rep.get('report_id', '—')}`\n"
                f"- Resumen: `{'sí' if last_rep.get('has_summary') else 'no'}`"
            )
        else:
            st.caption("Sin reportes detectados bajo `reports/` vía Gateway.")

    st.divider()
    st.markdown("### Enlaces públicos (navegador)")
    st.markdown(f"- Documentación OpenAPI: [{cfg.openapi_docs_url}]({cfg.openapi_docs_url})")
    phoenix_status = "Desconocido"
    if obs and isinstance(obs.get("phoenix"), dict):
        phoenix_status = obs["phoenix"].get("status", "unknown")
        from components.status_cards import STATUS_LABELS

        phoenix_status = STATUS_LABELS.get(normalize_status(phoenix_status), phoenix_status)
    st.markdown(
        f"- Phoenix ({phoenix_status}): [{cfg.phoenix_public_url}]({cfg.phoenix_public_url})"
    )
    st.caption(
        "Los enlaces son públicos para el navegador. "
        "Streamlit no consulta Phoenix ni Ollama directamente."
    )

    # Errores parciales no tumbaron toda la página
    partial_errors = []
    for name, result in (
        ("system/status", system_r),
        ("models", models_r),
        ("rag/status", rag_r),
        ("observability", obs_r),
    ):
        if result and not result.ok:
            partial_errors.append(f"`/{name}`: {result.error_kind}")
    if partial_errors and not bundle.get("gateway_down"):
        show_info("Respuestas parciales: " + ", ".join(partial_errors))
