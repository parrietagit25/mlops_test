"""Lectura segura de reportes bajo reports/."""

from __future__ import annotations

from fastapi import APIRouter

from api.errors import raise_api_error
from schemas.common import ErrorResponse
from schemas.reports import (
    ReportFileContentResponse,
    ReportLatestResponse,
    ReportListResponse,
    ReportSummary,
)
from services.report_store import (
    ReportAccessError,
    ReportNotFoundError,
    get_report,
    latest_report,
    list_reports,
    read_report_file,
)

router = APIRouter(tags=["reports"])


@router.get(
    "/reports",
    response_model=ReportListResponse,
    summary="Listar reportes de evaluación",
    description="Solo lee bajo `reports/YYYY-MM-DD/HHMMSS`. Sin path traversal.",
)
def reports_list() -> ReportListResponse:
    return list_reports()


@router.get(
    "/reports/latest",
    response_model=ReportLatestResponse,
    summary="Último reporte",
    description=(
        "Criterio: máximo lexicográfico de directorios "
        "`reports/YYYY-MM-DD/HHMMSS` (fecha, luego hora)."
    ),
)
def reports_latest() -> ReportLatestResponse:
    return latest_report()


@router.get(
    "/reports/{report_id}",
    response_model=ReportSummary,
    summary="Metadatos de un reporte",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def reports_get(report_id: str) -> ReportSummary:
    try:
        return get_report(report_id)
    except ReportAccessError as exc:
        raise_api_error(400, "INVALID_REPORT_ID", str(exc))
    except ReportNotFoundError as exc:
        raise_api_error(404, "REPORT_NOT_FOUND", str(exc))


@router.get(
    "/reports/{report_id}/files/{filename:path}",
    response_model=ReportFileContentResponse,
    summary="Contenido de un archivo de reporte",
    description=(
        "filename relativo al run (ej. summary.md o promptfoo/output.log). "
        "Extensiones: .md .txt .log .csv .json .html. Path jail obligatorio."
    ),
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
def reports_file(report_id: str, filename: str) -> ReportFileContentResponse:
    try:
        return read_report_file(report_id, filename)
    except ReportAccessError as exc:
        raise_api_error(400, "INVALID_REPORT_PATH", str(exc))
    except ReportNotFoundError as exc:
        raise_api_error(404, "REPORT_FILE_NOT_FOUND", str(exc))
