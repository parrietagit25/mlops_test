"""Validación y presentación de evaluaciones (UI-1E).

Contratos Gateway:
- POST /evals/{suite}/run → 202 EvalJobCreateResponse
- GET /evals/jobs → EvalJobListResponse
- GET /evals/jobs/{job_id} → EvalJobResponse

Suites: promptfoo | deepeval | ragas | security | all
Estados: queued | running | completed | failed | cancelled
"""

from __future__ import annotations

import re
from typing import Any

AUTHORIZED_SUITES = frozenset({"promptfoo", "deepeval", "ragas", "security", "all"})

SUMMARY_DISPLAY_MAX = 2_000
JOB_ID_RE = re.compile(r"^[a-f0-9]{32}$")
REPORT_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}$")

# Matriz documentada post EVAL-RUNTIME-1 (ailab-api: venvs DeepEval/Ragas en /opt;
# sin Node/npx ni garak).
SUITE_CATALOG: dict[str, dict[str, Any]] = {
    "promptfoo": {
        "label": "Promptfoo",
        "description": "Pruebas de prompts y flujos end-to-end vía promptfoo.",
        "availability": "no_disponible",
        "missing_deps": ["Node.js / npx (no instalado en ailab-api; EVAL-RUNTIME-2)"],
    },
    "deepeval": {
        "label": "DeepEval",
        "description": "Métricas LLM con pytest sobre evals/deepeval.",
        "availability": "disponible",
        "missing_deps": [],
    },
    "ragas": {
        "label": "Ragas",
        "description": "Evaluación RAG con métricas de faithfulness/relevancy.",
        "availability": "disponible",
        "missing_deps": ["Requiere índice RAG y embeddings Ollama activos"],
    },
    "security": {
        "label": "Security",
        "description": "Red teaming con garak y promptfoo redteam (best-effort).",
        "availability": "degradada",
        "missing_deps": ["garak no instalado", "npx no disponible en ailab-api"],
    },
    "all": {
        "label": "Run All",
        "description": "Ejecuta las cuatro suites en secuencia y genera summary.md.",
        "availability": "degradada",
        "missing_deps": ["Promptfoo/garak ausentes; hereda omisiones de security"],
    },
}

AVAILABILITY_LABELS = {
    "disponible": "Disponible",
    "degradada": "Degradada",
    "no_disponible": "No disponible",
    "desconocida": "Desconocida",
}

_DEGRADED_MARKERS = (
    "omitido",
    "no instalado",
    "no disponible",
    "npx no",
    "garak no",
    "se necesita node",
    "node.js/npx",
    "faltó",
    "falló u omitido",
    "probablemente por",
)


class EvalPayloadError(ValueError):
    """Error de validación de evaluaciones en UI."""


def assert_suite_allowed(suite_name: str) -> str:
    name = (suite_name or "").strip().lower()
    if not name:
        raise EvalPayloadError("No hay una suite seleccionada.")
    if name not in AUTHORIZED_SUITES:
        raise EvalPayloadError("Suite no autorizada en esta interfaz.")
    return name


def validate_job_id(job_id: str) -> str:
    jid = (job_id or "").strip()
    if not jid or not JOB_ID_RE.fullmatch(jid):
        raise EvalPayloadError("Identificador de job inválido.")
    return jid


def truncate_summary(text: str | None, max_len: int = SUMMARY_DISPLAY_MAX) -> str:
    raw = str(text or "").strip()
    if len(raw) <= max_len:
        return raw
    return raw[: max_len - 3] + "..."


def detect_skipped_tools(summary: str | None) -> list[str]:
    """Herramientas omitidas inferidas del resumen (solo presentación)."""
    if not summary:
        return []
    lower = summary.lower()
    found: list[str] = []
    if "garak" in lower and any(m in lower for m in ("omitido", "no instalado", "no está instalado")):
        found.append("garak")
    if "promptfoo" in lower or "npx" in lower:
        if any(m in lower for m in ("omitido", "no disponible", "node.js", "npx")):
            found.append("promptfoo")
    if "node.js" in lower or "se necesita npx" in lower:
        if "promptfoo" not in found:
            found.append("promptfoo (Node.js/npx)")
    return found


def summary_suggests_degradation(summary: str | None) -> bool:
    if not summary:
        return False
    lower = summary.lower()
    return any(marker in lower for marker in _DEGRADED_MARKERS)


def visual_job_status(job: dict[str, Any]) -> str:
    """Estado visual; no modifica el contrato del Gateway."""
    raw = str(job.get("status") or "").lower()
    summary = job.get("summary")
    error = job.get("error")
    if raw == "completed":
        if summary_suggests_degradation(summary) or detect_skipped_tools(summary):
            return "Completado con limitaciones"
        if error:
            return "Completado con limitaciones"
        return "Completado"
    if raw == "failed":
        return "Fallido"
    if raw == "running":
        return "En ejecución"
    if raw == "queued":
        return "En cola"
    if raw == "cancelled":
        return "Cancelado"
    return raw or "Desconocido"


def parse_job(data: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(data, dict):
        return None, "La respuesta del Gateway no tiene el formato esperado."
    job_id = data.get("job_id")
    suite = data.get("suite")
    status = data.get("status")
    if not job_id or not suite or not status:
        return None, "La respuesta del Gateway no tiene el formato esperado."
    return {
        "job_id": str(job_id),
        "suite": str(suite),
        "status": str(status),
        "created_at": data.get("created_at"),
        "started_at": data.get("started_at"),
        "finished_at": data.get("finished_at"),
        "duration_ms": data.get("duration_ms"),
        "summary": data.get("summary"),
        "report_ref": data.get("report_ref"),
        "error": data.get("error"),
        "message": data.get("message"),
    }, None


def parse_jobs_list(data: Any) -> tuple[list[dict[str, Any]], str | None]:
    if not isinstance(data, dict):
        return [], "La respuesta del Gateway no tiene el formato esperado."
    jobs_raw = data.get("jobs")
    if jobs_raw is None:
        return [], "La respuesta del Gateway no tiene el formato esperado."
    if not isinstance(jobs_raw, list):
        return [], "La respuesta del Gateway no tiene el formato esperado."
    jobs: list[dict[str, Any]] = []
    for item in jobs_raw:
        parsed, err = parse_job(item)
        if parsed:
            jobs.append(parsed)
    return jobs, None


def suite_is_active(jobs: list[dict[str, Any]], suite: str) -> bool:
    for job in jobs:
        if job.get("suite") == suite and str(job.get("status")) in {"queued", "running"}:
            return True
    return False


def latest_job_for_suite(jobs: list[dict[str, Any]], suite: str) -> dict[str, Any] | None:
    for job in jobs:
        if job.get("suite") == suite:
            return job
    return None


def safe_report_api_path(report_ref: str | None) -> str | None:
    ref = (report_ref or "").strip()
    if not ref or not REPORT_ID_RE.fullmatch(ref):
        return None
    return f"/reports/{ref}"


def humanize_eval_error(
    *,
    error_kind: str | None,
    error_code: str | None,
    error_message: str | None,
    status_code: int | None,
) -> str:
    if error_kind == "connection":
        return "Gateway no disponible. Verifica que ailab-api esté activo."
    if error_kind == "timeout":
        return "La solicitud de evaluación superó el tiempo de espera."
    if error_kind == "unavailable" or status_code == 503:
        return "El Gateway o un servicio requerido no está disponible temporalmente."
    if error_code == "DUPLICATE_SUITE" or status_code == 409:
        return "Ya hay un job en cola o en ejecución para esta suite."
    if error_code == "JOB_NOT_FOUND" or status_code == 404:
        return "El job no existe o se perdió tras reiniciar ailab-api."
    if status_code == 400:
        return error_message or "Suite o solicitud no válida."
    if status_code == 422:
        return "La solicitud no pasó la validación del Gateway."
    if status_code == 500 or error_kind == "server_error":
        return "Error interno del Gateway al procesar la evaluación."
    if error_kind == "invalid_json":
        return "La respuesta del Gateway no tiene el formato esperado."
    return error_message or "No se pudo completar la operación de evaluación."
