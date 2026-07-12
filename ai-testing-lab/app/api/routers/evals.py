"""Endpoints de evaluaciones con jobs in-memory."""

from __future__ import annotations

from fastapi import APIRouter

from api.errors import raise_api_error
from schemas.common import ErrorResponse
from schemas.evals import (
    EvalJobCreateResponse,
    EvalJobListResponse,
    EvalJobResponse,
    EvalSuite,
)
from services.eval_runner import run_suite
from services.job_manager import DuplicateSuiteError, JobRecord, get_job_manager

router = APIRouter(tags=["evals"])


def _to_response(job: JobRecord) -> EvalJobResponse:
    return EvalJobResponse(
        job_id=job.job_id,
        suite=job.suite,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        duration_ms=job.duration_ms,
        summary=job.summary,
        report_ref=job.report_ref,
        error=job.error,
    )


@router.post(
    "/evals/{suite}/run",
    response_model=EvalJobCreateResponse,
    status_code=202,
    summary="Encolar suite de evaluación autorizada",
    description=(
        "Whitelist estricta: promptfoo | deepeval | ragas | security | all. "
        "Ejecuta el script fijo correspondiente con subprocess shell=False. "
        "Jobs in-memory (se pierden al reiniciar). 409 si la suite ya está activa. "
        "Cancelación no implementada en Fase 1."
    ),
    responses={
        400: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def run_eval(suite: EvalSuite) -> EvalJobCreateResponse:
    manager = get_job_manager()

    def _runner(record: JobRecord) -> None:
        run_suite(suite, record)

    try:
        job = manager.submit(suite, _runner)
    except DuplicateSuiteError as exc:
        raise_api_error(409, "DUPLICATE_SUITE", str(exc))

    return EvalJobCreateResponse(
        job_id=job.job_id,
        suite=job.suite,
        status=job.status,
        created_at=job.created_at,
    )


@router.get(
    "/evals/jobs",
    response_model=EvalJobListResponse,
    summary="Listar jobs de evaluación",
)
def list_eval_jobs() -> EvalJobListResponse:
    jobs = get_job_manager().list_jobs()
    return EvalJobListResponse(jobs=[_to_response(j) for j in jobs])


@router.get(
    "/evals/jobs/{job_id}",
    response_model=EvalJobResponse,
    summary="Detalle de un job",
    responses={404: {"model": ErrorResponse}},
)
def get_eval_job(job_id: str) -> EvalJobResponse:
    job = get_job_manager().get(job_id)
    if job is None:
        raise_api_error(404, "JOB_NOT_FOUND", f"Job no encontrado: {job_id}")
    return _to_response(job)
