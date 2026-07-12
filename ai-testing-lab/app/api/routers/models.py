"""GET /models"""

from __future__ import annotations

from fastapi import APIRouter

from schemas.common import ErrorResponse
from schemas.models import ModelsResponse
from services.models_service import get_models

router = APIRouter(tags=["models"])


@router.get(
    "/models",
    response_model=ModelsResponse,
    summary="Modelos disponibles en Ollama",
    description=(
        "Lista modelos generativos y de embeddings vía HTTP a Ollama `/api/tags`. "
        "No ejecuta shell ni consulta Docker. Si Ollama no responde, "
        "`ollama_status=unavailable` y listas vacías (HTTP 200)."
    ),
    responses={503: {"model": ErrorResponse}},
)
def models() -> ModelsResponse:
    return get_models()
