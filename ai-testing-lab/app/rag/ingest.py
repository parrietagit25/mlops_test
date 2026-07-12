"""Ingesta mínima de documentos para RAG.

Diseño deliberadamente simple para la Fase 1:
- Chunking por tamaño fijo con overlap (sin dependencias de NLP pesadas).
- Embeddings vía Ollama (modelo configurable, ej. nomic-embed-text).
- Índice persistido como JSON plano (vector + texto + metadata).

Esto evita levantar un contenedor adicional de vector DB en el MVP. Si el
laboratorio crece, este módulo es el punto de reemplazo por Chroma/Qdrant/
pgvector (ver docs/architecture.md, sección "de aquí en adelante").

Implementación original.
"""

from __future__ import annotations

import json
from pathlib import Path

from core.config import get_settings
from core.llm_client import get_llm_client

SAMPLE_DOCS_DIR = Path(__file__).parent / "sample_docs"
UPLOADS_DIR = Path(__file__).parent / "uploads"
ALLOWED_GLOBS = ("*.txt", "*.md")


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
        if start <= 0:
            break
    return [c.strip() for c in chunks if c.strip()]


def _iter_docs(source_dirs: list[Path]) -> list[Path]:
    files: list[Path] = []
    for directory in source_dirs:
        if not directory.is_dir():
            continue
        for pattern in ALLOWED_GLOBS:
            files.extend(sorted(directory.glob(pattern)))
    # Deduplicar por nombre de archivo (uploads pueden sombrear sample_docs)
    by_name: dict[str, Path] = {}
    for path in files:
        by_name[path.name] = path
    return sorted(by_name.values(), key=lambda p: p.name)


def ingest_directory(source_dir: Path | None = None) -> dict:
    """Compatibilidad: ingesta un único directorio (por defecto sample_docs)."""
    dirs = [source_dir] if source_dir is not None else [SAMPLE_DOCS_DIR]
    return ingest_directories(dirs)


def ingest_directories(source_dirs: list[Path]) -> dict:
    settings = get_settings()
    llm = get_llm_client()
    paths = _iter_docs(source_dirs)

    records = []
    sources: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        chunks = chunk_text(text, settings.rag_chunk_size, settings.rag_chunk_overlap)
        embeddings = llm.embed(chunks) if chunks else []
        sources.append(path.name)
        for chunk, embedding in zip(chunks, embeddings):
            records.append({
                "source": path.name,
                "text": chunk,
                "embedding": embedding,
            })

    index_path = Path(settings.rag_index_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")

    return {
        "documents_indexed": len(sources),
        "chunks_indexed": len(records),
        "sources": sources,
    }


if __name__ == "__main__":
    result = ingest_directory()
    print(f"Ingesta completa: {result}")
