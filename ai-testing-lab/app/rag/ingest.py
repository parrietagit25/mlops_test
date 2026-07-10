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

import json
from pathlib import Path

from core.config import get_settings
from core.llm_client import get_llm_client

SAMPLE_DOCS_DIR = Path(__file__).parent / "sample_docs"


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


def ingest_directory(source_dir: Path | None = None) -> dict:
    settings = get_settings()
    llm = get_llm_client()
    source_dir = source_dir or SAMPLE_DOCS_DIR

    records = []
    for path in sorted(source_dir.glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        chunks = chunk_text(text, settings.rag_chunk_size, settings.rag_chunk_overlap)
        embeddings = llm.embed(chunks)
        for chunk, embedding in zip(chunks, embeddings):
            records.append({
                "source": path.name,
                "text": chunk,
                "embedding": embedding,
            })

    index_path = Path(settings.rag_index_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")

    return {"documents_indexed": len(list(source_dir.glob('*.txt'))), "chunks_indexed": len(records)}


if __name__ == "__main__":
    result = ingest_directory()
    print(f"Ingesta completa: {result}")
