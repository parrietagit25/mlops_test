"""Retriever mínimo: similitud coseno en memoria sobre el índice JSON.

Suficiente para un laboratorio local con decenas/cientos de chunks. No apto
para producción a escala (ver docs/architecture.md para el camino de
reemplazo por una base vectorial real).

Implementación original.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from core.config import get_settings
from core.llm_client import get_llm_client


@dataclass
class RetrievedChunk:
    source: str
    text: str
    score: float


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1e-8
    return float(np.dot(a, b) / denom)


def load_index() -> list[dict]:
    settings = get_settings()
    index_path = Path(settings.rag_index_path)
    if not index_path.exists():
        return []
    return json.loads(index_path.read_text(encoding="utf-8"))


def retrieve(query: str, top_k: int | None = None) -> list[RetrievedChunk]:
    settings = get_settings()
    records = load_index()
    if not records:
        return []

    llm = get_llm_client()
    query_embedding = np.array(llm.embed([query])[0])

    scored = []
    for record in records:
        score = _cosine_similarity(query_embedding, np.array(record["embedding"]))
        scored.append(RetrievedChunk(source=record["source"], text=record["text"], score=score))

    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[: top_k or settings.rag_top_k]
