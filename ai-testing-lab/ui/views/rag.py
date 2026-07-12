"""Vista RAG (UI-1D) — cliente HTTP de /rag/status, /rag/ingest y /rag/query."""

from __future__ import annotations

import time
from typing import Any

import streamlit as st

from api_client import ApiResult, GatewayClient
from components.messages import show_error, show_info, show_warning
from config import UIConfig
from rag_payload import (
    ALLOWED_EXTENSIONS,
    MAX_FILES_PER_REQUEST,
    MAX_UPLOAD_BYTES,
    QUERY_TOP_K_DEFAULT,
    QUERY_TOP_K_MAX,
    QUERY_TOP_K_MIN,
    QUERY_MAX_LEN,
    humanize_rag_error,
    parse_query_response,
    safe_status_fields,
    truncate_text,
    unique_sources,
    upload_selection_error,
    validate_query,
    validate_upload_batch,
)
from state import (
    RAG_STATUS_TTL_S,
    append_rag_history_entry,
    clear_rag_history,
    format_ui_timestamp,
    invalidate_rag_status_cache,
)


def _fetch_status(client: GatewayClient, *, force: bool = False) -> ApiResult:
    now = time.time()
    cached = st.session_state.rag_status_payload
    fetched_at = float(st.session_state.rag_status_fetched_at or 0.0)
    if (
        not force
        and isinstance(cached, dict)
        and (now - fetched_at) < RAG_STATUS_TTL_S
    ):
        return ApiResult(ok=True, status_code=200, data=cached)

    result = client.get_rag_status()
    if result.ok and isinstance(result.data, dict):
        st.session_state.rag_status_payload = result.data
        st.session_state.rag_status_fetched_at = now
    return result


def _render_status(client: GatewayClient) -> None:
    st.markdown("### Estado del RAG")
    if st.button("Actualizar estado RAG", use_container_width=False):
        invalidate_rag_status_cache()
        st.rerun()

    result = _fetch_status(client, force=False)
    if not result.ok:
        show_error(
            humanize_rag_error(
                error_kind=result.error_kind,
                error_code=result.error_code,
                error_message=result.error_message,
                status_code=result.status_code,
            )
        )
        return

    data = safe_status_fields(result.data if isinstance(result.data, dict) else None)
    available = bool(data.get("available"))
    if available:
        st.success("Índice RAG: disponible")
    else:
        show_warning("Índice RAG: no disponible")

    c1, c2, c3 = st.columns(3)
    c1.metric("Documentos", int(data.get("documents_indexed") or 0))
    c2.metric("Chunks", int(data.get("chunks_indexed") or 0))
    c3.metric("Embeddings", str(data.get("embedding_model") or "—"))

    exts = data.get("allowed_extensions") or sorted(ALLOWED_EXTENSIONS)
    st.caption(
        f"Extensiones: {', '.join(str(e) for e in exts)} · "
        f"Uploads: {'sí' if data.get('uploads_enabled', True) else 'no'} · "
        f"Última ingesta: {data.get('last_ingest_at') or 'No disponible'}"
    )
    if data.get("allowed_directory"):
        st.caption(f"Directorios lógicos: {data['allowed_directory']}")
    if data.get("warning"):
        st.info(str(data["warning"]))
    else:
        st.info("Implementación local mínima sin vector database.")


def _guess_content_type(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".md"):
        return "text/markdown"
    return "text/plain"


def _do_ingest(
    client: GatewayClient,
    *,
    files: list[tuple[str, bytes, str]] | None,
    label: str,
) -> None:
    if st.session_state.rag_ingest_in_progress or st.session_state.rag_query_in_progress:
        show_info("Hay una operación RAG en curso.")
        return
    st.session_state.rag_ingest_in_progress = True
    st.session_state.rag_last_error = None
    try:
        with st.spinner(label):
            result = client.ingest_rag_files(files)
        if not result.ok:
            st.session_state.rag_last_error = humanize_rag_error(
                error_kind=result.error_kind,
                error_code=result.error_code,
                error_message=result.error_message,
                status_code=result.status_code,
            )
            st.session_state.rag_last_ingest_result = None
            return
        if not isinstance(result.data, dict):
            st.session_state.rag_last_error = (
                "La respuesta del Gateway no tiene el formato esperado."
            )
            return
        st.session_state.rag_last_ingest_result = {
            "documents_indexed": result.data.get("documents_indexed"),
            "chunks_indexed": result.data.get("chunks_indexed"),
            "sources": result.data.get("sources") or [],
            "uploaded_files": result.data.get("uploaded_files") or [],
            "mode": result.data.get("mode"),
            "at": format_ui_timestamp(),
        }
        invalidate_rag_status_cache()
    except Exception:
        st.session_state.rag_last_error = "No se pudo completar la ingesta RAG."
        st.session_state.rag_last_ingest_result = None
    finally:
        st.session_state.rag_ingest_in_progress = False


def _render_ingest(client: GatewayClient) -> None:
    st.markdown("### Ingesta controlada")
    st.caption(
        f"Extensiones permitidas: {', '.join(sorted(ALLOWED_EXTENSIONS))} · "
        f"máximo {MAX_FILES_PER_REQUEST} archivos por solicitud. "
        "Los archivos pasan por el FastAPI Gateway; "
        "Streamlit no escribe directamente en el filesystem del backend."
    )
    st.caption(
        f"Límite real de AI Testing Lab: {MAX_UPLOAD_BYTES // 1024} KB por archivo "
        f"({MAX_UPLOAD_BYTES} bytes). "
        "Streamlit limita el uploader globalmente a 1 MB; la UI y el Gateway "
        "vuelven a validar el tope de 512000 bytes."
    )

    uploads = st.file_uploader(
        "Documentos (.txt / .md)",
        type=["txt", "md"],
        accept_multiple_files=True,
        key="rag_file_uploader",
        help=(
            "Límite visual Streamlit: 1 MB (config global). "
            "Límite real de la app: 512000 bytes, revalidado por UI y Gateway."
        ),
    )

    selection_error: str | None = None
    if uploads:
        st.markdown("**Selección actual**")
        for f in uploads:
            st.caption(f"{f.name} · {getattr(f, 'type', '') or 'text'} · {f.size} bytes")
        meta = [(f.name, int(f.size or 0)) for f in uploads]
        selection_error = upload_selection_error(meta)
        if selection_error:
            show_warning(selection_error)

    can_ingest_selection = (
        bool(uploads)
        and selection_error is None
        and not st.session_state.rag_ingest_in_progress
        and not st.session_state.rag_query_in_progress
    )

    b1, b2 = st.columns(2)
    with b1:
        ingest_sel = st.button(
            "Ingerir documentos",
            use_container_width=True,
            disabled=not can_ingest_selection,
        )
    with b2:
        ingest_sample = st.button(
            "Ingerir documentos de ejemplo",
            use_container_width=True,
            disabled=st.session_state.rag_ingest_in_progress
            or st.session_state.rag_query_in_progress,
            help="POST /rag/ingest sin archivos → reindexa sample_docs del Gateway.",
        )

    if ingest_sel and uploads:
        if selection_error:
            st.session_state.rag_last_error = selection_error
            return
        try:
            meta = [(f.name, int(f.size or 0)) for f in uploads]
            validate_upload_batch(meta)
            files = [
                (f.name, f.getvalue(), _guess_content_type(f.name)) for f in uploads
            ]
        except ValueError as exc:
            st.session_state.rag_last_error = str(exc)
            return
        _do_ingest(client, files=files, label="Ingestando documentos…")
        st.rerun()

    if ingest_sample:
        _do_ingest(client, files=None, label="Reindexando documentos de ejemplo…")
        st.rerun()

    last = st.session_state.rag_last_ingest_result
    if isinstance(last, dict):
        st.success(
            f"Ingesta OK · modo `{last.get('mode')}` · "
            f"docs={last.get('documents_indexed')} · chunks={last.get('chunks_indexed')}"
        )
        if last.get("uploaded_files"):
            st.caption("Subidos: " + ", ".join(str(x) for x in last["uploaded_files"]))
        if last.get("sources"):
            st.caption(
                "Fuentes indexadas: "
                + ", ".join(str(x) for x in unique_sources(
                    [{"source": s} for s in (last.get("sources") or [])]
                ))
            )


def _do_query(client: GatewayClient, cfg: UIConfig, question: str, top_k: int) -> None:
    if st.session_state.rag_query_in_progress or st.session_state.rag_ingest_in_progress:
        show_info("Hay una operación RAG en curso.")
        return
    try:
        q, k = validate_query(question=question, top_k=top_k)
    except ValueError as exc:
        st.session_state.rag_last_error = str(exc)
        return

    st.session_state.rag_query_in_progress = True
    st.session_state.rag_last_error = None
    started = time.perf_counter()
    try:
        with st.spinner("Consultando índice RAG…"):
            result = client.query_rag(q=q, top_k=k)
        duration_ms = (time.perf_counter() - started) * 1000.0
        if not result.ok:
            err = humanize_rag_error(
                error_kind=result.error_kind,
                error_code=result.error_code,
                error_message=result.error_message,
                status_code=result.status_code,
            )
            st.session_state.rag_last_error = err
            st.session_state.rag_last_query_result = None
            append_rag_history_entry(
                {
                    "executed_at": format_ui_timestamp(cfg.ui_timezone),
                    "question_summary": q[:120],
                    "status": "error",
                    "error": err,
                    "chunks_used": 0,
                    "unique_sources": [],
                    "duration_ms": duration_ms,
                }
            )
            return

        query, results, parse_err = parse_query_response(result.data)
        if parse_err:
            st.session_state.rag_last_error = parse_err
            st.session_state.rag_last_query_result = None
            return

        sources = unique_sources(results)
        payload = {
            "query": query or q,
            "results": results,
            "chunks_used": len(results),
            "unique_sources": sources,
            "duration_ms": duration_ms,
            "executed_at": format_ui_timestamp(cfg.ui_timezone),
        }
        st.session_state.rag_last_query_result = payload
        append_rag_history_entry(
            {
                "executed_at": payload["executed_at"],
                "question_summary": (query or q)[:120],
                "status": "ok",
                "error": None,
                "chunks_used": len(results),
                "unique_sources": sources,
                "duration_ms": duration_ms,
                "results_preview": [
                    {
                        "source": r.get("source"),
                        "text": truncate_text(str(r.get("text") or ""), 240),
                    }
                    for r in results[:5]
                ],
            }
        )
    except Exception:
        st.session_state.rag_last_error = "No se pudo completar la consulta RAG."
        st.session_state.rag_last_query_result = None
    finally:
        st.session_state.rag_query_in_progress = False


def _render_query(client: GatewayClient, cfg: UIConfig) -> None:
    st.markdown("### Consulta RAG")
    st.caption(
        "Usa `GET /rag/query` (retriever). Devuelve chunks con score; "
        "no genera una respuesta LLM. Para QA generativo usa Skills → rag_qa."
    )
    with st.form("rag_query_form", clear_on_submit=False):
        st.text_area(
            "Pregunta",
            key="rag_question",
            height=100,
            max_chars=QUERY_MAX_LEN,
        )
        st.number_input(
            "top_k",
            min_value=QUERY_TOP_K_MIN,
            max_value=QUERY_TOP_K_MAX,
            step=1,
            key="rag_top_k",
            help="Cantidad máxima de chunks a recuperar (1–10).",
        )
        submitted = st.form_submit_button(
            "Consultar RAG",
            use_container_width=True,
            disabled=st.session_state.rag_query_in_progress
            or st.session_state.rag_ingest_in_progress,
        )
    if submitted:
        _do_query(
            client,
            cfg,
            st.session_state.rag_question,
            int(st.session_state.rag_top_k or QUERY_TOP_K_DEFAULT),
        )
        st.rerun()

    last = st.session_state.rag_last_query_result
    if not isinstance(last, dict):
        return

    st.markdown("### Resultados de recuperación")
    chunks = int(last.get("chunks_used") or 0)
    sources = last.get("unique_sources") or []
    st.caption(
        f"Chunks utilizados: {chunks} · "
        f"Fuentes únicas: {', '.join(sources) if sources else 'ninguna'} · "
        f"Duración: {(last.get('duration_ms') or 0) / 1000.0:.2f} s"
    )
    if chunks == 0:
        show_info(
            "Sin chunks recuperados. El índice puede estar vacío "
            "o la consulta no encontró similitud útil."
        )
        return

    results = last.get("results") or []
    for idx, item in enumerate(results, start=1):
        src = item.get("source") or "desconocido"
        score = item.get("score")
        title = f"Chunk {idx} · {src}"
        if score is not None:
            try:
                title += f" · score {float(score):.3f}"
            except (TypeError, ValueError):
                pass
        with st.expander(title, expanded=(idx == 1)):
            st.markdown(
                truncate_text(str(item.get("text") or "")),
                unsafe_allow_html=False,
            )


def _render_history(cfg: UIConfig) -> None:
    history = st.session_state.rag_query_history or []
    st.markdown("### Historial de consultas")
    st.caption(
        f"Solo sesión del navegador (máx. 20). Zona: {cfg.ui_timezone}."
    )
    st.button(
        "Limpiar historial RAG",
        disabled=len(history) == 0,
        on_click=clear_rag_history,
    )
    if not history:
        st.caption("Sin consultas todavía.")
        return
    for idx, entry in enumerate(history):
        label = (
            f"{entry.get('executed_at', '?')} · "
            f"{entry.get('status', '?')} · "
            f"chunks={entry.get('chunks_used', 0)}"
        )
        with st.expander(label, expanded=(idx == 0)):
            st.caption(f"Pregunta: {entry.get('question_summary') or '—'}")
            srcs = entry.get("unique_sources") or []
            st.caption(
                "Fuentes únicas: " + (", ".join(srcs) if srcs else "ninguna")
            )
            if entry.get("error"):
                show_error(str(entry["error"]))
            for prev in entry.get("results_preview") or []:
                st.markdown(
                    f"**{prev.get('source')}** — {prev.get('text')}",
                    unsafe_allow_html=False,
                )


def render(client: GatewayClient, cfg: UIConfig) -> None:
    st.markdown("## RAG")
    st.caption(
        "Ingiere documentos permitidos y consulta el índice RAG local "
        "exclusivamente mediante el FastAPI Gateway."
    )
    st.info("Implementación local mínima sin vector database.")
    st.caption(f"Timeout RAG: {cfg.rag_read_timeout_s:.0f}s")

    if st.session_state.rag_last_error:
        show_error(st.session_state.rag_last_error)

    _render_status(client)
    st.divider()
    _render_ingest(client)
    st.divider()
    _render_query(client, cfg)
    st.divider()
    _render_history(cfg)
