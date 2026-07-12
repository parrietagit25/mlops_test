"""GET /observability — metadatos Phoenix (URL solo server-side)."""

from __future__ import annotations

from fastapi import APIRouter

from core.config import get_settings
from schemas.observability import ObservabilityResponse, PhoenixInfo
from services.phoenix_probe import probe_phoenix

router = APIRouter(tags=["observability"])


@router.get(
    "/observability",
    response_model=ObservabilityResponse,
    summary="Información de observabilidad",
    description=(
        "Devuelve la URL configurada de Phoenix para que la UI muestre un enlace. "
        "No acepta URL del cliente. No hace de proxy."
    ),
)
def observability() -> ObservabilityResponse:
    settings = get_settings()
    enabled = settings.enable_tracing
    status = "unavailable"
    if enabled:
        status = "available" if probe_phoenix() else "unavailable"
    else:
        status = "disabled"
    return ObservabilityResponse(
        phoenix=PhoenixInfo(
            enabled=enabled,
            url=settings.phoenix_ui_url,
            status=status,
        )
    )
