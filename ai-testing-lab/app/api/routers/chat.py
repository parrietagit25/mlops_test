"""POST /chat"""

from __future__ import annotations

from fastapi import APIRouter

from api.errors import raise_api_error
from schemas.chat import ChatRequest, ChatResponse
from schemas.common import ErrorResponse
from services.chat_service import run_chat
from services.ollama_probe import OllamaUnavailableError

router = APIRouter(tags=["chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat libre vía Gateway",
    description=(
        "Envía una conversación al modelo local a través de `LLMClient` "
        "(Ollama). No acepta URLs de proveedor ni comandos del sistema. "
        "Roles permitidos: system, user, assistant."
    ),
    responses={
        400: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        return run_chat(request)
    except LookupError as exc:
        raise_api_error(400, "MODEL_NOT_FOUND", str(exc))
    except OllamaUnavailableError as exc:
        raise_api_error(503, "OLLAMA_UNAVAILABLE", str(exc))
    except Exception as exc:  # pragma: no cover
        raise_api_error(500, "CHAT_FAILED", "Error interno al generar la respuesta.", details=str(exc))
