"""Estado consolidado del laboratorio (sin secretos ni rutas host)."""

from __future__ import annotations

from core.config import get_settings
from schemas.observability import ComponentStatus, SystemStatusResponse
from services.job_manager import get_job_manager
from services.ollama_probe import probe_ollama
from services.phoenix_probe import probe_phoenix
from services.rag_status import get_rag_status
from services.report_store import latest_report


def get_system_status() -> SystemStatusResponse:
    settings = get_settings()
    ollama_ok = probe_ollama()
    phoenix_ok = probe_phoenix() if settings.enable_tracing else False
    rag = get_rag_status()

    components = [
        ComponentStatus(name="gateway", status="available"),
        ComponentStatus(name="ollama", status="available" if ollama_ok else "unavailable"),
        ComponentStatus(
            name="phoenix",
            status=(
                "available"
                if phoenix_ok
                else ("disabled" if not settings.enable_tracing else "unavailable")
            ),
        ),
    ]

    last_eval = None
    jobs = get_job_manager().list_jobs()
    if jobs:
        j = jobs[0]
        last_eval = {
            "job_id": j.job_id,
            "suite": j.suite.value,
            "status": j.status,
            "finished_at": j.finished_at,
        }

    last_rep = None
    latest = latest_report().report
    if latest:
        last_rep = {
            "report_id": latest.report_id,
            "created_at": latest.created_at,
            "has_summary": latest.has_summary,
        }

    return SystemStatusResponse(
        gateway="available",
        components=components,
        chat_model=settings.ollama_chat_model,
        embedding_model=settings.ollama_embed_model,
        rag={
            "available": rag.available,
            "documents_indexed": rag.documents_indexed,
            "chunks_indexed": rag.chunks_indexed,
        },
        last_evaluation=last_eval,
        last_report=last_rep,
        environment=settings.environment,
        phase="1-local",
    )
