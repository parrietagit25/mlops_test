"""Schemas de observabilidad y system status."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PhoenixInfo(BaseModel):
    enabled: bool
    url: str = Field(..., examples=["http://127.0.0.1:6006"])
    status: str = Field(..., examples=["available", "unavailable"])


class ObservabilityResponse(BaseModel):
    phoenix: PhoenixInfo


class ComponentStatus(BaseModel):
    name: str
    status: str


class SystemStatusResponse(BaseModel):
    gateway: str
    components: list[ComponentStatus]
    chat_model: str
    embedding_model: str
    rag: dict
    last_evaluation: dict | None = None
    last_report: dict | None = None
    environment: str = "local"
    phase: str = "1-local"
