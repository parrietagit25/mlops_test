"""GET /system/status"""

from __future__ import annotations

from fastapi import APIRouter

from schemas.observability import SystemStatusResponse
from services.system_status import get_system_status

router = APIRouter(tags=["system"])


@router.get(
    "/system/status",
    response_model=SystemStatusResponse,
    summary="Estado consolidado del laboratorio",
    description=(
        "Resumen seguro: gateway, Ollama, Phoenix, modelos, RAG, última eval/reporte. "
        "No expone secretos, env completo ni rutas host."
    ),
)
def system_status() -> SystemStatusResponse:
    return get_system_status()
