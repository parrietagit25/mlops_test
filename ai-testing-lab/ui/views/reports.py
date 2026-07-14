"""Vista Reportes (UI-1F) — lectura segura vía FastAPI Gateway."""

from __future__ import annotations

from typing import Any

import streamlit as st

from api_client import GatewayClient
from components.messages import show_error, show_info, show_warning
from config import UIConfig
from reports_payload import (
    filter_reports_by_suite,
    humanize_report_error,
    parse_file_content,
    parse_latest_report,
    parse_report_summary,
    parse_reports_list,
    safe_report_file_public_path,
    safe_report_public_path,
    validate_report_filename,
    validate_report_id,
)
from state import (
    clear_reports_errors,
    clear_reports_viewer,
    format_ui_timestamp,
    mark_reports_refreshed,
)

_SUITE_FILTERS = ("todas", "promptfoo", "deepeval", "ragas", "security")


def _public_url(cfg: UIConfig, path: str | None) -> str | None:
    if not path:
        return None
    return f"{cfg.api_public_url.rstrip('/')}{path}"


def _set_error_from_result(result) -> None:
    st.session_state.reports_last_error = humanize_report_error(
        error_kind=result.error_kind,
        error_code=result.error_code,
        error_message=result.error_message,
        status_code=result.status_code,
    )


def _refresh_list(client: GatewayClient) -> None:
    result = client.list_reports()
    if not result.ok:
        _set_error_from_result(result)
        return
    reports, count, err = parse_reports_list(result.data)
    if err:
        st.session_state.reports_last_error = err
        return
    st.session_state.reports_list = reports
    st.session_state.reports_list_count = count
    clear_reports_errors()
    mark_reports_refreshed()


def _refresh_latest(client: GatewayClient) -> None:
    result = client.get_latest_report()
    if not result.ok:
        _set_error_from_result(result)
        return
    report, criterion, err = parse_latest_report(result.data)
    if err:
        st.session_state.reports_last_error = err
        return
    st.session_state.reports_latest = report
    st.session_state.reports_latest_criterion = criterion
    clear_reports_errors()
    mark_reports_refreshed()


def _load_detail(client: GatewayClient, report_id: str) -> None:
    if st.session_state.reports_request_in_progress:
        show_info("Hay una carga de reporte en curso.")
        return
    try:
        rid = validate_report_id(report_id)
    except ValueError as exc:
        st.session_state.reports_last_error = str(exc)
        return

    st.session_state.reports_request_in_progress = True
    st.session_state.reports_last_error = None
    try:
        result = client.get_report(rid)
    finally:
        st.session_state.reports_request_in_progress = False

    if not result.ok:
        _set_error_from_result(result)
        return
    detail, err = parse_report_summary(result.data)
    if err or not detail:
        st.session_state.reports_last_error = err or "Detalle de reporte incompleto."
        return
    st.session_state.reports_selected_id = rid
    st.session_state.reports_selected_detail = detail
    st.session_state.reports_selected_file = None
    st.session_state.reports_file_content = None
    clear_reports_errors()


def _load_file(client: GatewayClient, report_id: str, filename: str) -> None:
    if st.session_state.reports_request_in_progress:
        show_info("Hay una carga de archivo en curso.")
        return
    try:
        rid = validate_report_id(report_id)
        fname = validate_report_filename(filename)
    except ValueError as exc:
        st.session_state.reports_last_error = str(exc)
        return

    st.session_state.reports_request_in_progress = True
    try:
        result = client.get_report_file(rid, fname)
    finally:
        st.session_state.reports_request_in_progress = False

    if not result.ok:
        _set_error_from_result(result)
        st.session_state.reports_file_content = None
        return
    content, err = parse_file_content(result.data)
    if err or not content:
        st.session_state.reports_last_error = err or "Contenido de archivo incompleto."
        st.session_state.reports_file_content = None
        return
    st.session_state.reports_selected_file = fname
    st.session_state.reports_file_content = content
    clear_reports_errors()


def _render_report_card(report: dict[str, Any] | None, *, title: str) -> None:
    if not report:
        st.caption(f"{title}: ninguno disponible.")
        return
    rid = report.get("report_id") or "—"
    suites = ", ".join(report.get("suites_present") or []) or "—"
    st.markdown(f"**{title}:** `{rid}` · estado `{report.get('status')}`")
    st.caption(
        f"Creado: {report.get('created_at') or '—'} · "
        f"Suites: {suites} · "
        f"Archivos: {len(report.get('files') or [])} · "
        f"Bytes: {report.get('total_size_bytes') or 0}"
    )
    if report.get("summary_excerpt"):
        with st.expander("Extracto del resumen", expanded=False):
            st.text(report["summary_excerpt"])


def render(client: GatewayClient, cfg: UIConfig) -> None:
    st.markdown("## Reportes")
    st.caption(
        "Consulta reportes de evaluación mediante el FastAPI Gateway. "
        "Streamlit no lee el directorio `reports/` directamente."
    )
    show_warning(
        "Los reportes viven en disco del laboratorio y se sirven solo vía Gateway "
        "(identificadores YYYY-MM-DD_HHMMSS, archivos con extensión permitida)."
    )

    if st.session_state.reports_last_error:
        show_error(st.session_state.reports_last_error)

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        if st.button("Actualizar lista", key="reports_refresh_list"):
            _refresh_list(client)
            st.rerun()
    with c2:
        if st.button("Actualizar último", key="reports_refresh_latest"):
            _refresh_latest(client)
            st.rerun()
    with c3:
        st.caption(
            f"Última actualización: {st.session_state.reports_last_refresh or '—'}"
        )

    # Carga inicial perezosa
    if not st.session_state.reports_list and st.session_state.reports_last_refresh is None:
        _refresh_list(client)
        _refresh_latest(client)

    st.markdown("### Último reporte")
    _render_report_card(st.session_state.reports_latest, title="Latest")
    if st.session_state.reports_latest_criterion:
        st.caption(f"Criterio Gateway: {st.session_state.reports_latest_criterion}")
    latest = st.session_state.reports_latest
    if latest and latest.get("report_id"):
        if st.button("Abrir último en detalle", key="reports_open_latest"):
            _load_detail(client, latest["report_id"])
            st.rerun()

    st.divider()
    st.markdown("### Historial de reportes")
    st.selectbox("Filtrar por suite presente", options=list(_SUITE_FILTERS), key="reports_suite_filter")
    reports = filter_reports_by_suite(
        list(st.session_state.reports_list or []),
        st.session_state.reports_suite_filter,
    )
    st.caption(f"Mostrando {len(reports)} de {st.session_state.reports_list_count} reportes.")

    if not reports:
        st.caption("Sin reportes. Ejecuta evaluaciones o pulsa «Actualizar lista».")
    else:
        for rep in reports:
            rid = rep.get("report_id") or ""
            label = (
                f"`{rid}` · {rep.get('status')} · "
                f"{', '.join(rep.get('suites_present') or []) or 'sin suites'}"
            )
            if st.button(label, key=f"reports_pick_{rid}", use_container_width=True):
                _load_detail(client, rid)
                st.rerun()

    st.divider()
    st.markdown("### Detalle del reporte seleccionado")
    detail = st.session_state.reports_selected_detail
    selected_id = st.session_state.reports_selected_id
    if not detail or not selected_id:
        st.caption("Selecciona un reporte de la lista o el último.")
    else:
        _render_report_card(detail, title="Seleccionado")
        pub = _public_url(cfg, safe_report_public_path(selected_id))
        if pub:
            st.link_button("Metadatos en Gateway", pub)

        files = detail.get("files") or []
        if not files:
            show_info("Este reporte no lista archivos legibles.")
        else:
            names = [f["name"] for f in files]
            choice = st.selectbox(
                "Archivo",
                options=names,
                key="reports_file_select",
                index=names.index(st.session_state.reports_selected_file)
                if st.session_state.reports_selected_file in names
                else 0,
            )
            sizes = {f["name"]: f.get("size_bytes") for f in files}
            st.caption(f"Tamaño informado: {sizes.get(choice, '—')} bytes")
            b1, b2 = st.columns(2)
            with b1:
                if st.button(
                    "Cargar archivo",
                    key="reports_load_file",
                    disabled=st.session_state.reports_request_in_progress,
                ):
                    _load_file(client, selected_id, choice)
                    st.rerun()
            with b2:
                if st.button("Limpiar selección", key="reports_clear_sel"):
                    clear_reports_viewer()
                    st.rerun()

            file_pub = _public_url(
                cfg, safe_report_file_public_path(selected_id, choice)
            )
            if file_pub:
                st.link_button("Abrir archivo en Gateway", file_pub)

    st.divider()
    st.markdown("### Visor de contenido")
    content = st.session_state.reports_file_content
    if not content:
        st.caption("Carga un archivo permitido (.md, .txt, .log, .csv, .json, .html).")
        return

    st.markdown(
        f"**`{content.get('filename')}`** · "
        f"{content.get('media_type')} · "
        f"{content.get('size_bytes')} bytes"
    )
    if content.get("truncated"):
        show_warning(
            "El Gateway truncó este archivo (límite de bytes). El contenido mostrado puede estar incompleto."
        )
    # Texto plano siempre: no renderizar HTML del reporte (evita XSS).
    st.text(content.get("content") or "")
    st.caption(f"Vista cargada: {format_ui_timestamp(cfg.ui_timezone)}")
