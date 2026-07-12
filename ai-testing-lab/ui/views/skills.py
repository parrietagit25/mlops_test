"""Vista Skills (UI-1C) — cliente HTTP de GET /skills y POST /agents/{skill}/run."""

from __future__ import annotations

import time
from typing import Any

import streamlit as st

from api_client import ApiResult, GatewayClient
from components.messages import show_error, show_info, show_warning
from config import UIConfig
from skills_payload import (
    RAG_TOP_K_DEFAULT,
    RAG_TOP_K_MAX,
    RAG_TOP_K_MIN,
    SUMMARIZER_MAX_SENTENCES_DEFAULT,
    SUMMARIZER_MAX_SENTENCES_MAX,
    SUMMARIZER_MAX_SENTENCES_MIN,
    UI_TEXT_MAX_LEN,
    assert_skill_allowed,
    authorized_skill_names,
    build_skill_payload,
    humanize_skill_error,
    parse_skill_result,
    safe_metadata_for_display,
    skill_description,
)
from state import (
    SKILLS_LIST_TTL_S,
    append_skills_history_entry,
    build_skills_history_entry,
    clear_skills_history,
    invalidate_skills_cache,
)


def _fetch_skills(client: GatewayClient, *, force: bool = False) -> ApiResult:
    now = time.time()
    cached = st.session_state.skills_list
    fetched_at = float(st.session_state.skills_list_fetched_at or 0.0)
    if (
        not force
        and isinstance(cached, list)
        and (now - fetched_at) < SKILLS_LIST_TTL_S
    ):
        return ApiResult(ok=True, status_code=200, data=cached)

    result = client.get_skills()
    if result.ok and isinstance(result.data, list):
        st.session_state.skills_list = result.data
        st.session_state.skills_list_fetched_at = now
    return result


def _apply_skill_selection(available: list[str]) -> None:
    selected = st.session_state.skills_selected
    if available:
        if selected not in available:
            st.session_state.skills_selected = available[0]
    else:
        st.session_state.skills_selected = None


def _gateway_status(client: GatewayClient) -> str:
    health = client.health()
    if health.ok:
        return "disponible"
    if health.error_kind == "connection":
        return "no disponible"
    if health.error_kind == "timeout":
        return "timeout"
    return "degradado"


def _format_result_caption(
    *,
    skill: str,
    metadata: dict[str, Any] | None,
    duration_ms: float | None,
) -> str:
    parts = [f"Skill: {skill}"]
    meta = safe_metadata_for_display(metadata)
    if "chunks_used" in meta:
        parts.append(f"Chunks: {meta['chunks_used']}")
    if duration_ms is not None:
        parts.append(f"Duración: {duration_ms / 1000.0:.2f} s")
    sources = meta.get("sources")
    if sources:
        parts.append("Fuentes: " + ", ".join(str(s) for s in sources[:5]))
    return " · ".join(parts)


def _render_summarizer_form() -> dict[str, Any] | None:
    with st.form("skills_summarizer_form", clear_on_submit=False):
        st.text_area(
            "Texto a resumir",
            key="skills_summarizer_text",
            height=160,
            max_chars=UI_TEXT_MAX_LEN,
            help="Campo `text` del contrato SummarizerInput.",
        )
        st.number_input(
            "Máximo de oraciones",
            min_value=SUMMARIZER_MAX_SENTENCES_MIN,
            max_value=SUMMARIZER_MAX_SENTENCES_MAX,
            step=1,
            key="skills_summarizer_max_sentences",
            help="Campo `max_sentences` (1–10, default 3).",
        )
        submitted = st.form_submit_button(
            "Ejecutar summarizer",
            use_container_width=True,
            disabled=st.session_state.skills_request_in_progress,
        )
    if not submitted:
        return None
    return {
        "text": st.session_state.skills_summarizer_text,
        "max_sentences": st.session_state.skills_summarizer_max_sentences
        or SUMMARIZER_MAX_SENTENCES_DEFAULT,
    }


def _render_rag_qa_form(rag_warning: str | None) -> dict[str, Any] | None:
    if rag_warning:
        show_warning(rag_warning)
    with st.form("skills_rag_qa_form", clear_on_submit=False):
        st.text_area(
            "Pregunta",
            key="skills_rag_question",
            height=120,
            max_chars=UI_TEXT_MAX_LEN,
            help="Campo `question` del contrato RagQAInput.",
        )
        st.number_input(
            "top_k",
            min_value=RAG_TOP_K_MIN,
            max_value=RAG_TOP_K_MAX,
            step=1,
            key="skills_rag_top_k",
            help="Número de fragmentos de contexto (1–10, default 3).",
        )
        submitted = st.form_submit_button(
            "Ejecutar rag_qa",
            use_container_width=True,
            disabled=st.session_state.skills_request_in_progress,
        )
    if not submitted:
        return None
    return {
        "question": st.session_state.skills_rag_question,
        "top_k": st.session_state.skills_rag_top_k or RAG_TOP_K_DEFAULT,
    }


def _run_selected_skill(
    client: GatewayClient,
    *,
    skill_name: str,
    available: list[str],
    form_values: dict[str, Any],
) -> None:
    if st.session_state.skills_request_in_progress:
        show_info("Ya hay una ejecución de skill en curso.")
        return

    try:
        skill = assert_skill_allowed(skill_name, available)
        payload = build_skill_payload(skill, form_values)
    except ValueError as exc:
        st.session_state.skills_last_error = str(exc)
        return

    st.session_state.skills_last_error = None
    st.session_state.skills_request_in_progress = True
    started = time.perf_counter()

    try:
        with st.spinner(f"Ejecutando `{skill}`…"):
            result = client.run_skill(skill, payload)
        duration_ms = (time.perf_counter() - started) * 1000.0

        if not result.ok:
            err = humanize_skill_error(
                error_kind=result.error_kind,
                error_code=result.error_code,
                error_message=result.error_message,
                status_code=result.status_code,
            )
            st.session_state.skills_last_error = err
            st.session_state.skills_last_result = None
            append_skills_history_entry(
                build_skills_history_entry(
                    skill=skill,
                    payload=payload,
                    status="error",
                    error=err,
                    duration_ms=duration_ms,
                )
            )
            return

        output, metadata, parse_err = parse_skill_result(result.data)
        if parse_err:
            st.session_state.skills_last_error = parse_err
            st.session_state.skills_last_result = None
            append_skills_history_entry(
                build_skills_history_entry(
                    skill=skill,
                    payload=payload,
                    status="error",
                    error=parse_err,
                    duration_ms=duration_ms,
                )
            )
            return

        safe_meta = safe_metadata_for_display(metadata)
        st.session_state.skills_last_result = {
            "skill": skill,
            "output": output,
            "metadata": safe_meta,
            "duration_ms": duration_ms,
        }
        append_skills_history_entry(
            build_skills_history_entry(
                skill=skill,
                payload=payload,
                status="ok",
                output=output,
                metadata=safe_meta,
                duration_ms=duration_ms,
            )
        )
    except Exception:
        st.session_state.skills_last_error = (
            "No se pudo completar la ejecución de la skill."
        )
        st.session_state.skills_last_result = None
    finally:
        st.session_state.skills_request_in_progress = False


def _render_history() -> None:
    history = st.session_state.skills_history or []
    st.markdown("### Historial de ejecuciones")
    st.caption(
        "Solo en esta sesión del navegador (máx. 20). "
        "Se pierde al cerrar o reiniciar el contenedor."
    )
    st.button(
        "Limpiar historial",
        disabled=len(history) == 0,
        on_click=clear_skills_history,
        use_container_width=False,
    )
    if not history:
        st.caption("Sin ejecuciones todavía.")
        return

    for idx, entry in enumerate(history):
        label = (
            f"{entry.get('executed_at', '?')} · {entry.get('skill', '?')} · "
            f"{entry.get('status', '?')}"
        )
        with st.expander(label, expanded=(idx == 0)):
            st.caption(f"Entrada: {entry.get('input_summary') or '—'}")
            if entry.get("status") == "ok" and entry.get("output"):
                st.markdown(str(entry["output"]), unsafe_allow_html=False)
            if entry.get("error"):
                show_error(str(entry["error"]))
            cap = _format_result_caption(
                skill=str(entry.get("skill") or ""),
                metadata=entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {},
                duration_ms=entry.get("duration_ms"),
            )
            st.caption(cap)


def render(client: GatewayClient, cfg: UIConfig) -> None:
    st.markdown("## Skills")
    st.caption(
        "Ejecuta capacidades especializadas mediante el FastAPI Gateway. "
        "La interfaz no importa ni ejecuta skills directamente."
    )
    st.caption(
        f"Timeout de ejecución: {cfg.skill_read_timeout_s:.0f}s · "
        "Historial solo en sesión Streamlit."
    )

    gw = _gateway_status(client)
    if gw == "disponible":
        st.success(f"Gateway: {gw}")
    else:
        show_warning(f"Gateway: {gw}")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Actualizar skills", use_container_width=True):
            invalidate_skills_cache()
            st.rerun()
    with c2:
        st.caption("Cache corto de GET /skills (TTL ~30s).")

    skills_result = _fetch_skills(client, force=False)
    skills_data = skills_result.data if skills_result.ok and isinstance(skills_result.data, list) else None
    available = authorized_skill_names(skills_data)
    _apply_skill_selection(available)

    if not skills_result.ok:
        show_error(
            humanize_skill_error(
                error_kind=skills_result.error_kind,
                error_code=skills_result.error_code,
                error_message=skills_result.error_message,
                status_code=skills_result.status_code,
            )
        )
        show_info("La página permanece disponible. Reintenta con Actualizar skills.")
    elif not available:
        show_warning("No hay skills autorizadas disponibles desde el Gateway.")

    if available:
        st.selectbox(
            "Skill",
            options=available,
            key="skills_selected",
            help="Solo skills del Gateway que la UI soporta (summarizer, rag_qa).",
        )
        selected = st.session_state.skills_selected
        desc = skill_description(skills_data, selected or "")
        if desc:
            st.info(desc)

        rag_warning = None
        if selected == "rag_qa":
            rag = client.rag_status()
            if rag.ok and isinstance(rag.data, dict):
                docs = int(rag.data.get("documents_indexed") or 0)
                available_flag = bool(rag.data.get("available"))
                if not available_flag or docs <= 0:
                    rag_warning = (
                        "El índice RAG no tiene documentos indexados o no está "
                        "disponible. rag_qa puede responder sin contexto útil. "
                        "La administración del índice queda para UI-1D."
                    )

        form_values = None
        if selected == "summarizer":
            form_values = _render_summarizer_form()
        elif selected == "rag_qa":
            form_values = _render_rag_qa_form(rag_warning)

        if form_values is not None and selected:
            _run_selected_skill(
                client,
                skill_name=selected,
                available=available,
                form_values=form_values,
            )
            st.rerun()

    if st.session_state.skills_last_error:
        show_error(st.session_state.skills_last_error)

    last = st.session_state.skills_last_result
    if isinstance(last, dict) and last.get("output"):
        st.markdown("### Resultado")
        st.markdown(str(last["output"]), unsafe_allow_html=False)
        st.caption(
            _format_result_caption(
                skill=str(last.get("skill") or ""),
                metadata=last.get("metadata") if isinstance(last.get("metadata"), dict) else {},
                duration_ms=last.get("duration_ms"),
            )
        )

    _render_history()
