"""Modelos de error y utilidades comunes para respuestas de la API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str = Field(..., examples=["INVALID_SUITE"])
    message: str = Field(..., examples=["Evaluation suite is not allowed."])
    details: Any = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class StatusLiteral:
    """Estados genéricos reutilizables en documentación."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
