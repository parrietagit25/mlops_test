"""Estado seguro del índice RAG (sin rutas absolutas del host)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from core.config import get_settings
from schemas.rag import RagStatusResponse


def get_rag_status() -> RagStatusResponse:
    settings = get_settings()
    index_path = Path(settings.rag_index_path)
    documents: set[str] = set()
    chunks = 0
    last_ingest: str | None = None
    available = False

    if index_path.exists():
        try:
            records = json.loads(index_path.read_text(encoding="utf-8"))
            if isinstance(records, list):
                chunks = len(records)
                for rec in records:
                    src = rec.get("source")
                    if src:
                        documents.add(str(src))
                available = chunks > 0
            mtime = datetime.fromtimestamp(index_path.stat().st_mtime, tz=timezone.utc)
            last_ingest = mtime.isoformat()
        except Exception:
            available = False

    return RagStatusResponse(
        available=available,
        embedding_model=settings.ollama_embed_model,
        documents_indexed=len(documents),
        chunks_indexed=chunks,
        allowed_directory="rag/sample_docs + rag/uploads",
        allowed_extensions=sorted(settings.rag_allowed_extensions),
        last_ingest_at=last_ingest,
        uploads_enabled=True,
    )
