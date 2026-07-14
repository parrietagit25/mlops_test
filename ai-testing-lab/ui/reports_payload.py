"""Validación y presentación de reportes (UI-1F).

Contratos Gateway:
- GET /reports
- GET /reports/latest
- GET /reports/{report_id}
- GET /reports/{report_id}/files/{filename}
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

ALLOWED_REPORT_EXTENSIONS = frozenset({".json", ".html", ".md", ".txt", ".csv", ".log"})
REPORT_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}$")
CONTENT_DISPLAY_MAX = 50_000
EXCERPT_DISPLAY_MAX = 2_000


class ReportPayloadError(ValueError):
    """Error de validación de reportes en UI."""


def validate_report_id(report_id: str) -> str:
    rid = (report_id or "").strip()
    if not rid or not REPORT_ID_RE.fullmatch(rid):
        raise ReportPayloadError(
            "Identificador de reporte inválido (formato YYYY-MM-DD_HHMMSS)."
        )
    if "/" in rid or "\\" in rid or ".." in rid:
        raise ReportPayloadError("Identificador de reporte inválido.")
    return rid


def validate_report_filename(filename: str) -> str:
    raw = (filename or "").strip().replace("\\", "/")
    if not raw or raw.startswith("/") or ":" in raw:
        raise ReportPayloadError("Nombre de archivo de reporte inválido.")
    parts = raw.split("/")
    if any(p in {"", ".", ".."} for p in parts):
        raise ReportPayloadError("Nombre de archivo de reporte inválido.")
    name = parts[-1]
    if "." not in name:
        raise ReportPayloadError("El archivo de reporte debe tener extensión permitida.")
    ext = "." + name.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_REPORT_EXTENSIONS:
        raise ReportPayloadError(f"Extensión no permitida: {ext}")
    return "/".join(parts)


def truncate_text(text: str | None, max_len: int = CONTENT_DISPLAY_MAX) -> str:
    raw = str(text or "")
    if len(raw) <= max_len:
        return raw
    return raw[: max_len - 3] + "..."


def safe_report_public_path(report_id: str | None) -> str | None:
    try:
        rid = validate_report_id(report_id or "")
    except ReportPayloadError:
        return None
    return f"/reports/{rid}"


def safe_report_file_public_path(report_id: str | None, filename: str | None) -> str | None:
    try:
        rid = validate_report_id(report_id or "")
        fname = validate_report_filename(filename or "")
    except ReportPayloadError:
        return None
    encoded = "/".join(quote(part, safe="") for part in fname.split("/"))
    return f"/reports/{rid}/files/{encoded}"


def parse_report_summary(data: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(data, dict):
        return None, "La respuesta del Gateway no tiene el formato esperado."
    rid = data.get("report_id")
    if not rid:
        return None, "La respuesta del Gateway no tiene el formato esperado."
    try:
        validate_report_id(str(rid))
    except ReportPayloadError:
        return None, "Identificador de reporte inválido en la respuesta."

    files_raw = data.get("files") or []
    files: list[dict[str, Any]] = []
    if isinstance(files_raw, list):
        for item in files_raw:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not name:
                continue
            try:
                safe_name = validate_report_filename(str(name))
            except ReportPayloadError:
                continue
            files.append(
                {
                    "name": safe_name,
                    "size_bytes": int(item.get("size_bytes") or 0),
                    "content_type_hint": str(
                        item.get("content_type_hint") or "text/plain"
                    ),
                }
            )

    suites = data.get("suites_present") or []
    if not isinstance(suites, list):
        suites = []

    return {
        "report_id": str(rid),
        "date": str(data.get("date") or ""),
        "time": str(data.get("time") or ""),
        "created_at": data.get("created_at"),
        "suites_present": [str(s) for s in suites],
        "has_summary": bool(data.get("has_summary")),
        "summary_excerpt": truncate_text(
            data.get("summary_excerpt"), EXCERPT_DISPLAY_MAX
        )
        or None,
        "files": files,
        "total_size_bytes": int(data.get("total_size_bytes") or 0),
        "status": str(data.get("status") or "available"),
    }, None


def parse_reports_list(data: Any) -> tuple[list[dict[str, Any]], int, str | None]:
    if not isinstance(data, dict):
        return [], 0, "La respuesta del Gateway no tiene el formato esperado."
    reports_raw = data.get("reports")
    if reports_raw is None:
        return [], 0, "La respuesta del Gateway no tiene el formato esperado."
    if not isinstance(reports_raw, list):
        return [], 0, "La respuesta del Gateway no tiene el formato esperado."
    reports: list[dict[str, Any]] = []
    for item in reports_raw:
        parsed, _err = parse_report_summary(item)
        if parsed:
            reports.append(parsed)
    count = data.get("count")
    try:
        count_i = int(count) if count is not None else len(reports)
    except (TypeError, ValueError):
        count_i = len(reports)
    return reports, count_i, None


def parse_latest_report(data: Any) -> tuple[dict[str, Any] | None, str | None, str | None]:
    if not isinstance(data, dict):
        return None, None, "La respuesta del Gateway no tiene el formato esperado."
    criterion = data.get("criterion")
    report_raw = data.get("report")
    if report_raw is None:
        return None, str(criterion) if criterion else None, None
    parsed, err = parse_report_summary(report_raw)
    if err:
        return None, str(criterion) if criterion else None, err
    return parsed, str(criterion) if criterion else None, None


def parse_file_content(data: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(data, dict):
        return None, "La respuesta del Gateway no tiene el formato esperado."
    rid = data.get("report_id")
    filename = data.get("filename")
    content = data.get("content")
    if rid is None or filename is None or content is None:
        return None, "La respuesta del Gateway no tiene el formato esperado."
    try:
        validate_report_id(str(rid))
        safe_name = validate_report_filename(str(filename))
    except ReportPayloadError as exc:
        return None, str(exc)
    return {
        "report_id": str(rid),
        "filename": safe_name,
        "media_type": str(data.get("media_type") or "text/plain"),
        "size_bytes": int(data.get("size_bytes") or 0),
        "truncated": bool(data.get("truncated")),
        "content": truncate_text(str(content), CONTENT_DISPLAY_MAX),
    }, None


def filter_reports_by_suite(
    reports: list[dict[str, Any]], suite: str | None
) -> list[dict[str, Any]]:
    if not suite or suite == "todas":
        return list(reports)
    return [r for r in reports if suite in (r.get("suites_present") or [])]


def parse_observability(data: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(data, dict):
        return None, "La respuesta del Gateway no tiene el formato esperado."
    phoenix = data.get("phoenix")
    if not isinstance(phoenix, dict):
        return None, "La respuesta del Gateway no tiene el formato esperado."
    url = phoenix.get("url")
    # Solo aceptar URL ya entregada por el Gateway (no editable por usuario).
    safe_url = str(url).strip() if url else None
    if safe_url and not (
        safe_url.startswith("http://127.0.0.1")
        or safe_url.startswith("https://127.0.0.1")
        or safe_url.startswith("http://localhost")
    ):
        # Aún mostrar status; ocultar URL sospechosa fuera de loopback típico.
        # Compose usa 127.0.0.1; si viene otra, no la exponemos como enlace.
        safe_url = None
    return {
        "enabled": bool(phoenix.get("enabled")),
        "status": str(phoenix.get("status") or "unavailable"),
        "url": safe_url,
    }, None


def humanize_report_error(
    *,
    error_kind: str | None,
    error_code: str | None,
    error_message: str | None,
    status_code: int | None,
) -> str:
    if error_kind == "connection":
        return "Gateway no disponible. Verifica que ailab-api esté activo."
    if error_kind == "timeout":
        return "La solicitud de reportes superó el tiempo de espera."
    if error_kind == "unavailable" or status_code == 503:
        return "El Gateway o un servicio requerido no está disponible temporalmente."
    if error_code in {"REPORT_NOT_FOUND", "REPORT_FILE_NOT_FOUND"} or status_code == 404:
        return "El reporte o archivo no existe."
    if error_code in {"INVALID_REPORT_ID", "INVALID_REPORT_PATH"} or status_code == 400:
        return error_message or "Identificador o ruta de reporte no válida."
    if status_code == 422:
        return "La solicitud no pasó la validación del Gateway."
    if status_code == 500 or error_kind == "server_error":
        return "Error interno del Gateway al leer reportes."
    if error_kind == "invalid_json":
        return "La respuesta del Gateway no tiene el formato esperado."
    return error_message or "No se pudo completar la operación de reportes."
