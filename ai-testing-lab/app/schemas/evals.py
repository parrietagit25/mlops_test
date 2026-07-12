"""Schemas de evaluaciones y jobs."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class EvalSuite(str, Enum):
    promptfoo = "promptfoo"
    deepeval = "deepeval"
    ragas = "ragas"
    security = "security"
    all = "all"


JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


class EvalJobCreateResponse(BaseModel):
    job_id: str
    suite: EvalSuite
    status: JobStatus
    created_at: str
    message: str = Field(
        default=(
            "Job encolado. Los jobs viven solo en memoria del proceso API "
            "(se pierden al reiniciar el contenedor)."
        )
    )


class EvalJobResponse(BaseModel):
    job_id: str
    suite: EvalSuite
    status: JobStatus
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: float | None = None
    summary: str | None = None
    report_ref: str | None = Field(
        default=None,
        description="Identificador lógico del reporte bajo reports/, si existe.",
    )
    error: str | None = None


class EvalJobListResponse(BaseModel):
    jobs: list[EvalJobResponse]
    note: str = (
        "Administrador de jobs in-memory (Fase 1 Local). "
        "No es una cola distribuida; el estado se pierde al reiniciar la API."
    )
