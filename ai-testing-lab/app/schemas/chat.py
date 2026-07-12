"""Schemas de chat."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ChatRole = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    role: ChatRole
    content: str = Field(..., min_length=1, max_length=16_000)

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("El contenido del mensaje no puede estar vacío.")
        return value


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=40)
    model: str | None = Field(
        default=None,
        max_length=128,
        description="Modelo Ollama. Si se omite, usa el configurado por defecto.",
        examples=["llama3.2:1b"],
    )
    temperature: float = Field(default=0.2, ge=0.0, le=1.5)
    max_tokens: int = Field(default=512, ge=1, le=2048)

    @model_validator(mode="after")
    def limit_total_chars(self) -> ChatRequest:
        total = sum(len(m.content) for m in self.messages)
        if total > 32_000:
            raise ValueError("La longitud total de los mensajes supera el límite (32000).")
        if self.model is not None:
            cleaned = self.model.strip()
            if not cleaned or any(c in cleaned for c in ("/", "\\", " ", ";", "|", "&", "`")):
                raise ValueError("Nombre de modelo inválido.")
            self.model = cleaned
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "messages": [
                        {"role": "system", "content": "Eres un asistente útil."},
                        {"role": "user", "content": "Hola"},
                    ],
                    "model": "llama3.2:1b",
                    "temperature": 0.2,
                    "max_tokens": 512,
                }
            ]
        }
    }


class ChatResponse(BaseModel):
    reply: str
    model: str
    temperature: float
    max_tokens: int
    duration_ms: float
    trace_id: str | None = Field(
        default=None,
        description="Identificador OTEL/Phoenix si el tracing está activo; null si no hay span válido.",
    )
