"""API gateway propia de ai-testing-lab (FastAPI).

Expone:
- GET  /health              -> chequeo de vida
- GET  /skills               -> lista de skills de agente disponibles
- POST /agents/{skill}/run   -> ejecuta una skill de agente
- POST /rag/ingest           -> (re)indexa app/rag/sample_docs
- GET  /rag/query            -> consulta el índice RAG sin pasar por un skill

Este gateway es el punto único de entrada que consumen promptfoo, DeepEval,
Ragas y los scripts de scripts/, para que las pruebas siempre hablen con la
misma superficie que usaría un consumidor real del laboratorio.

Implementación original.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agents.runtime import SkillNotFoundError, get_runtime
from core.tracing import setup_tracing
from rag.ingest import ingest_directory
from rag.retriever import retrieve

setup_tracing()

app = FastAPI(
    title="ai-testing-lab API",
    description="Gateway propio para agentes, RAG y prompts del laboratorio.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/skills")
def list_skills() -> list[dict]:
    return get_runtime().list_skills()


class RunSkillRequest(BaseModel):
    payload: dict


@app.post("/agents/{skill_name}/run")
def run_skill(skill_name: str, request: RunSkillRequest) -> dict:
    try:
        result = get_runtime().run_skill(skill_name, request.payload)
    except SkillNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result.model_dump()


@app.post("/rag/ingest")
def rag_ingest() -> dict:
    return ingest_directory()


@app.get("/rag/query")
def rag_query(q: str, top_k: int = 3) -> dict:
    chunks = retrieve(q, top_k=top_k)
    return {
        "query": q,
        "results": [{"source": c.source, "text": c.text, "score": c.score} for c in chunks],
    }
