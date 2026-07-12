"""API gateway propia de ai-testing-lab (FastAPI).

Endpoints legacy (Fase 1, contratos preservados):
- GET  /health
- GET  /skills
- POST /agents/{skill}/run
- POST /rag/ingest   (también acepta uploads opcionales vía router UI-0B)
- GET  /rag/query

Contratos UI-0B (routers):
- POST /chat, GET /models, GET /rag/status
- POST /evals/{suite}/run, GET /evals/jobs, GET /evals/jobs/{id}
- GET /reports, /reports/latest, /reports/{id}, /reports/{id}/files/{filename}
- GET /observability, GET /system/status

Implementación original.
"""

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agents.runtime import SkillNotFoundError, get_runtime
from api.errors import error_payload, http_exception_handler
from api.routers import chat, evals, models, observability, rag_ext, reports, system
from core.tracing import setup_tracing
from rag.retriever import retrieve
from schemas.common import ErrorResponse

setup_tracing()

app = FastAPI(
    title="ai-testing-lab API",
    description=(
        "Gateway propio para agentes, RAG, chat, evaluaciones y reportes del "
        "laboratorio local (Fase 1). Streamlit (futuro) debe consumir solo esta API."
    ),
    version="0.2.0",
)

app.add_exception_handler(HTTPException, http_exception_handler)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=error_payload("VALIDATION_ERROR", "Solicitud inválida.", details=exc.errors()),
    )


# --- Routers UI-0B -----------------------------------------------------------
app.include_router(chat.router)
app.include_router(models.router)
app.include_router(rag_ext.router)
app.include_router(evals.router)
app.include_router(reports.router)
app.include_router(observability.router)
app.include_router(system.router)


# --- Endpoints legacy (contratos sin cambio de shape) ------------------------
@app.get(
    "/health",
    tags=["health"],
    summary="Liveness",
    responses={200: {"description": "Proceso vivo"}},
)
def health() -> dict:
    return {"status": "ok"}


@app.get("/skills", tags=["agents"], summary="Listar skills")
def list_skills() -> list[dict]:
    return get_runtime().list_skills()


class RunSkillRequest(BaseModel):
    payload: dict


@app.post(
    "/agents/{skill_name}/run",
    tags=["agents"],
    summary="Ejecutar skill",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def run_skill(skill_name: str, request: RunSkillRequest) -> dict:
    try:
        result = get_runtime().run_skill(skill_name, request.payload)
    except SkillNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=error_payload("SKILL_NOT_FOUND", str(exc)),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=error_payload("INVALID_PAYLOAD", str(exc)),
        ) from exc
    return result.model_dump()


@app.get(
    "/rag/query",
    tags=["rag"],
    summary="Consulta RAG (retriever)",
)
def rag_query(q: str, top_k: int = 3) -> dict:
    chunks = retrieve(q, top_k=top_k)
    return {
        "query": q,
        "results": [{"source": c.source, "text": c.text, "score": c.score} for c in chunks],
    }
