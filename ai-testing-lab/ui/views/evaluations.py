"""Vista Evaluaciones (UI-1E) — jobs vía FastAPI Gateway."""

from __future__ import annotations

from typing import Any

import streamlit as st

from api_client import ApiResult, GatewayClient
from components.messages import show_error, show_info, show_warning
from config import UIConfig
from evals_payload import (
    AUTHORIZED_SUITES,
    AVAILABILITY_LABELS,
    SUITE_CATALOG,
    assert_suite_allowed,
    detect_skipped_tools,
    humanize_eval_error,
    latest_job_for_suite,
    parse_job,
    parse_jobs_list,
    safe_report_api_path,
    suite_is_active,
    truncate_summary,
    validate_job_id,
    visual_job_status,
)
from state import (
    clear_eval_errors,
    format_ui_timestamp,
    reset_eval_request_flag,
    set_eval_jobs,
    upsert_eval_job,
)

_SUITE_ORDER = ("promptfoo", "deepeval", "ragas", "security", "all")
_TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})


def _abbrev_job_id(job_id: str | None) -> str:
    if not job_id:
        return "—"
    return f"{job_id[:8]}…"


def _format_duration(ms: float | int | None) -> str:
    if ms is None:
        return "—"
    try:
        value = float(ms)
    except (TypeError, ValueError):
        return "—"
    if value < 1000:
        return f"{value:.0f} ms"
    return f"{value / 1000:.1f} s"


def _public_report_url(cfg: UIConfig, report_ref: str | None) -> str | None:
    path = safe_report_api_path(report_ref)
    if not path:
        return None
    return f"{cfg.api_public_url.rstrip('/')}{path}"


def _gateway_status(client: GatewayClient) -> str:
    health = client.health()
    if health.ok:
        return "disponible"
    if health.error_kind == "connection":
        return "no disponible"
    if health.error_kind == "timeout":
        return "timeout"
    return "degradado"


def _refresh_jobs(client: GatewayClient) -> ApiResult:
    result = client.get_evaluation_jobs()
    if result.ok:
        jobs, parse_err = parse_jobs_list(result.data)
        if parse_err:
            st.session_state.eval_last_error = parse_err
        else:
            set_eval_jobs(jobs)
            clear_eval_errors()
    return result


def _refresh_job(client: GatewayClient, job_id: str) -> ApiResult:
    result = client.get_evaluation_job(job_id)
    if result.ok:
        job, parse_err = parse_job(result.data)
        if parse_err:
            st.session_state.eval_last_error = parse_err
        elif job:
            upsert_eval_job(job)
            clear_eval_errors()
            if str(job.get("status")) in _TERMINAL_STATUSES:
                if st.session_state.eval_active_job_id == job_id:
                    st.session_state.eval_active_job_id = job_id
    elif result.status_code == 404 and st.session_state.eval_active_job_id == job_id:
        st.session_state.eval_last_error = humanize_eval_error(
            error_kind=result.error_kind,
            error_code=result.error_code or "JOB_NOT_FOUND",
            error_message=result.error_message,
            status_code=404,
        )
        st.session_state.eval_active_job_id = None
    return result


def _run_suite(client: GatewayClient, suite: str) -> None:
    if st.session_state.eval_request_in_progress:
        show_info("Ya hay una solicitud de evaluación en curso.")
        return

    try:
        name = assert_suite_allowed(suite)
    except ValueError as exc:
        st.session_state.eval_last_error = str(exc)
        return

    jobs = list(st.session_state.eval_jobs or [])
    if suite_is_active(jobs, name):
        st.session_state.eval_last_error = humanize_eval_error(
            error_kind="client_error",
            error_code="DUPLICATE_SUITE",
            error_message=None,
            status_code=409,
        )
        show_warning(st.session_state.eval_last_error)
        return

    st.session_state.eval_request_in_progress = True
    st.session_state.eval_last_error = None
    st.session_state.eval_selected_suite = name

    try:
        with st.spinner(f"Encolando `{name}`…"):
            result = client.run_evaluation(name)
    finally:
        reset_eval_request_flag()

    if not result.ok:
        st.session_state.eval_last_error = humanize_eval_error(
            error_kind=result.error_kind,
            error_code=result.error_code,
            error_message=result.error_message,
            status_code=result.status_code,
        )
        return

    job, parse_err = parse_job(result.data)
    if parse_err or not job:
        st.session_state.eval_last_error = parse_err or "No se recibió job_id del Gateway."
        return

    jid = job["job_id"]
    st.session_state.eval_active_job_id = jid
    st.session_state.eval_selected_job_id = jid
    upsert_eval_job(job)
    show_info(f"Job `{_abbrev_job_id(jid)}` encolado ({job.get('status')}).")


def _availability_badge(availability: str) -> str:
    return AVAILABILITY_LABELS.get(availability, AVAILABILITY_LABELS["desconocida"])


def _render_limitations(gateway: str) -> None:
    st.markdown("### Estado y limitaciones")
    st.warning(
        "Los jobs viven en memoria y se pierden al reiniciar ailab-api."
    )
    st.caption(f"Gateway: **{gateway}** · Sin cancelación · Sin persistencia de jobs.")
    st.markdown(
        "- **Promptfoo** requiere Node.js/npx, no instalado en la imagen `ailab-api`.\n"
        "- **garak** no está instalado; la suite **security** puede completar con omisiones.\n"
        "- **DeepEval** y **Ragas** pueden tardar (venv + dependencias en primer uso).\n"
        "- `trace_id` puede ser null en otras vistas; los reportes se referencian por ID lógico."
    )


def _render_suite_cards(client: GatewayClient, jobs: list[dict[str, Any]]) -> None:
    st.markdown("### Suites disponibles")
    cols = st.columns(len(_SUITE_ORDER))
    for col, suite in zip(cols, _SUITE_ORDER):
        meta = SUITE_CATALOG.get(suite, {})
        label = meta.get("label", suite)
        desc = meta.get("description", "")
        availability = meta.get("availability", "desconocida")
        missing = meta.get("missing_deps") or []
        latest = latest_job_for_suite(jobs, suite)
        with col:
            st.markdown(f"**{label}**")
            st.caption(desc)
            badge = _availability_badge(availability)
            if availability == "no_disponible":
                st.error(badge)
            elif availability == "degradada":
                st.warning(badge)
            elif availability == "disponible":
                st.success(badge)
            else:
                st.info(badge)
            if missing:
                st.caption("Dependencias: " + "; ".join(str(m) for m in missing))
            if latest:
                st.caption(
                    f"Último job: `{_abbrev_job_id(latest.get('job_id'))}` · "
                    f"{visual_job_status(latest)}"
                )
            else:
                st.caption("Último job: ninguno en sesión")
            active = suite_is_active(jobs, suite)
            if st.button(
                f"Ejecutar {label}",
                key=f"eval_run_{suite}",
                use_container_width=True,
                disabled=st.session_state.eval_request_in_progress or active,
            ):
                _run_suite(client, suite)


def _render_active_job(client: GatewayClient) -> None:
    st.markdown("### Ejecución activa")
    active_id = st.session_state.eval_active_job_id
    if not active_id:
        st.caption("No hay job activo seleccionado.")
        return

    try:
        validate_job_id(active_id)
    except ValueError:
        st.session_state.eval_active_job_id = None
        return

    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("Actualizar job", key="eval_refresh_active"):
            _refresh_job(client, active_id)
            st.rerun()
    with c2:
        st.caption(f"Job activo: `{_abbrev_job_id(active_id)}`")

    job = next(
        (j for j in (st.session_state.eval_jobs or []) if j.get("job_id") == active_id),
        None,
    )
    if not job:
        result = _refresh_job(client, active_id)
        if result.ok:
            job, _ = parse_job(result.data)
        else:
            show_error(
                st.session_state.eval_last_error
                or humanize_eval_error(
                    error_kind=result.error_kind,
                    error_code=result.error_code,
                    error_message=result.error_message,
                    status_code=result.status_code,
                )
            )
            return

    if job:
        _render_job_summary(job)


def _render_history(client: GatewayClient) -> None:
    st.markdown("### Historial de jobs")
    c1, c2, c3 = st.columns([1, 2, 2])
    with c1:
        if st.button("Actualizar historial", key="eval_refresh_history"):
            result = _refresh_jobs(client)
            if not result.ok:
                st.session_state.eval_last_error = humanize_eval_error(
                    error_kind=result.error_kind,
                    error_code=result.error_code,
                    error_message=result.error_message,
                    status_code=result.status_code,
                )
            st.rerun()
    with c2:
        options = ["todas", *sorted(AUTHORIZED_SUITES)]
        st.selectbox(
            "Filtrar por suite",
            options=options,
            key="eval_history_filter",
        )
    with c3:
        st.caption(
            f"Última actualización: {st.session_state.eval_last_refresh or '—'}"
        )

    jobs = list(st.session_state.eval_jobs or [])
    filt = st.session_state.eval_history_filter
    if filt and filt != "todas":
        jobs = [j for j in jobs if j.get("suite") == filt]

    if not jobs:
        st.caption("Sin jobs en el historial. Usa «Actualizar historial» o ejecuta una suite.")
        return

    for job in jobs:
        jid = job.get("job_id", "")
        label = (
            f"`{_abbrev_job_id(jid)}` · {job.get('suite')} · "
            f"{visual_job_status(job)} · {job.get('created_at') or '—'}"
        )
        if st.button(label, key=f"eval_select_{jid}", use_container_width=True):
            st.session_state.eval_selected_job_id = jid
            st.rerun()


def _render_job_detail(client: GatewayClient, cfg: UIConfig) -> None:
    st.markdown("### Detalle del job seleccionado")
    selected = st.session_state.eval_selected_job_id
    if not selected:
        st.caption("Selecciona un job del historial o ejecuta una suite.")
        return

    try:
        validate_job_id(selected)
    except ValueError as exc:
        st.session_state.eval_selected_job_id = None
        show_error(str(exc))
        return

    job = next(
        (j for j in (st.session_state.eval_jobs or []) if j.get("job_id") == selected),
        None,
    )
    if st.button("Refrescar detalle", key="eval_refresh_detail"):
        _refresh_job(client, selected)
        st.rerun()

    if not job:
        result = _refresh_job(client, selected)
        if result.ok:
            job, err = parse_job(result.data)
            if err:
                show_error(err)
                return
        else:
            show_error(
                st.session_state.eval_last_error
                or humanize_eval_error(
                    error_kind=result.error_kind,
                    error_code=result.error_code,
                    error_message=result.error_message,
                    status_code=result.status_code,
                )
            )
            return

    if job:
        _render_job_summary(job, cfg=cfg, expanded=True)


def _render_job_summary(
    job: dict[str, Any],
    *,
    cfg: UIConfig | None = None,
    expanded: bool = False,
) -> None:
    status_visual = visual_job_status(job)
    raw_status = str(job.get("status") or "—")
    skipped = detect_skipped_tools(job.get("summary"))
    suite = job.get("suite") or "—"

    st.markdown(f"**Estado:** {status_visual} (`{raw_status}`)")
    st.markdown(f"**Suite:** {suite}")
    st.markdown(f"**Job ID:** `{_abbrev_job_id(job.get('job_id'))}`")
    st.caption(
        f"Creado: {job.get('created_at') or '—'} · "
        f"Inicio: {job.get('started_at') or '—'} · "
        f"Fin: {job.get('finished_at') or '—'} · "
        f"Duración: {_format_duration(job.get('duration_ms'))}"
    )

    if skipped:
        st.warning("Herramientas omitidas (según resumen): " + ", ".join(skipped))
    elif raw_status == "completed" and suite != "promptfoo":
        st.caption(f"Herramienta principal: {SUITE_CATALOG.get(suite, {}).get('label', suite)}")

    summary = truncate_summary(job.get("summary"))
    if summary:
        with st.expander("Resumen", expanded=expanded):
            st.text(summary)
    elif raw_status in _TERMINAL_STATUSES:
        st.caption("Sin resumen disponible.")

    err = job.get("error")
    if err:
        show_error(str(err))

    report_ref = job.get("report_ref")
    if report_ref:
        st.markdown(f"**Reporte:** `{report_ref}`")
        if cfg:
            url = _public_report_url(cfg, report_ref)
            if url:
                st.link_button("Ver reporte en Gateway", url)
            else:
                show_warning("Referencia de reporte con formato no válido.")
    elif raw_status == "completed" and suite in {"security", "all"}:
        show_warning(
            "Job completado sin reporte persistente (común en security cuando garak/promptfoo faltan)."
        )


def render(client: GatewayClient, cfg: UIConfig) -> None:
    st.markdown("## Evaluaciones")
    st.caption(
        "Ejecuta suites autorizadas mediante el FastAPI Gateway y consulta su progreso. "
        "Streamlit no ejecuta comandos ni scripts directamente."
    )

    gateway = _gateway_status(client)
    _render_limitations(gateway)

    if st.session_state.eval_last_error:
        show_error(st.session_state.eval_last_error)

    jobs = list(st.session_state.eval_jobs or [])
    _render_suite_cards(client, jobs)
    st.divider()
    _render_active_job(client)
    st.divider()
    _render_history(client)
    st.divider()
    _render_job_detail(client, cfg)
