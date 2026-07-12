"""Extensiones RAG: status + ingest con uploads opcionales."""

from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from api.errors import raise_api_error
from rag.ingest import SAMPLE_DOCS_DIR, UPLOADS_DIR, ingest_directories
from schemas.common import ErrorResponse
from schemas.rag import RagIngestResponse, RagStatusResponse
from services.rag_status import get_rag_status
from services.rag_upload import RagUploadError, save_uploads

router = APIRouter(tags=["rag"])


@router.get(
    "/rag/status",
    response_model=RagStatusResponse,
    summary="Estado del índice RAG",
    description=(
        "Metadatos seguros del índice local (sin rutas absolutas del host). "
        "Advertencia: RAG mínimo sin vector DB."
    ),
)
def rag_status() -> RagStatusResponse:
    return get_rag_status()


@router.post(
    "/rag/ingest",
    response_model=RagIngestResponse,
    summary="Ingesta RAG (sample_docs y/o uploads)",
    description=(
        "Sin archivos: reindexa `rag/sample_docs` (comportamiento Fase 1 original). "
        "Con multipart `files`: acepta solo `.txt`/`.md`, tamaño limitado, nombres "
        "sanitizados, guardados en `rag/uploads` (sin ejecutar contenido). "
        "Luego indexa sample_docs + uploads."
    ),
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def rag_ingest(
    files: list[UploadFile] | None = File(default=None),
) -> RagIngestResponse:
    uploaded: list[str] = []
    dirs = [SAMPLE_DOCS_DIR]
    mode = "sample_docs"

    # FastAPI puede pasar lista vacía
    real_files = [f for f in (files or []) if f.filename]
    if real_files:
        try:
            uploaded = await save_uploads(real_files)
        except RagUploadError as exc:
            status = 413 if exc.code == "FILE_TOO_LARGE" else 400
            raise_api_error(status, exc.code, str(exc))
        dirs.append(UPLOADS_DIR)
        mode = "sample_docs+uploads"

    try:
        result = ingest_directories(dirs)
    except Exception as exc:
        raise_api_error(500, "INGEST_FAILED", "No se pudo completar la ingesta.", details=str(exc))

    return RagIngestResponse(
        documents_indexed=result["documents_indexed"],
        chunks_indexed=result["chunks_indexed"],
        sources=result.get("sources") or [],
        uploaded_files=uploaded,
        mode=mode,
    )
