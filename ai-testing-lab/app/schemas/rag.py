"""Schemas de RAG (status e ingest enriquecido)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RagStatusResponse(BaseModel):
    available: bool
    embedding_model: str
    documents_indexed: int
    chunks_indexed: int
    allowed_directory: str = Field(
        ...,
        description="Directorio lógico permitido para documentos (relativo al lab, sin rutas host).",
        examples=["rag/sample_docs", "rag/uploads"],
    )
    allowed_extensions: list[str]
    last_ingest_at: str | None = None
    warning: str = Field(
        default=(
            "RAG mínimo de Fase 1: índice JSON + similitud coseno. "
            "No hay vector database dedicada."
        )
    )
    uploads_enabled: bool = True


class RagIngestResponse(BaseModel):
    documents_indexed: int
    chunks_indexed: int
    sources: list[str] = Field(default_factory=list)
    uploaded_files: list[str] = Field(default_factory=list)
    mode: str = Field(
        ...,
        description="sample_docs | uploads | sample_docs+uploads",
        examples=["sample_docs"],
    )
