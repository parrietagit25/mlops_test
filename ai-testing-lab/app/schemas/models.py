"""Schemas de listado de modelos."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelInfo(BaseModel):
    name: str
    default: bool = False
    family: str | None = None
    parameter_size: str | None = None


class ModelsResponse(BaseModel):
    chat_models: list[ModelInfo] = Field(default_factory=list)
    embedding_models: list[ModelInfo] = Field(default_factory=list)
    ollama_status: str = Field(..., examples=["available", "unavailable"])
