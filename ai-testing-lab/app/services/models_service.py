"""Listado de modelos vía Ollama /api/tags (HTTP, sin shell)."""

from __future__ import annotations

from core.config import get_settings
from schemas.models import ModelInfo, ModelsResponse
from services.ollama_probe import OllamaUnavailableError, list_ollama_tags


_EMBED_HINTS = ("embed", "nomic-embed", "bge-", "e5-", "minilm", "mxbai-embed")


def _is_embedding(name: str, details: dict | None) -> bool:
    lower = name.lower()
    if any(h in lower for h in _EMBED_HINTS):
        return True
    caps = (details or {}).get("families") or []
    family = ((details or {}).get("family") or "").lower()
    if "bert" in family or any("bert" in str(c).lower() for c in caps):
        # Heurística: nomic-bert suele ser embedding
        if "embed" in lower or "nomic" in lower:
            return True
    return False


def get_models() -> ModelsResponse:
    settings = get_settings()
    try:
        raw = list_ollama_tags()
    except OllamaUnavailableError:
        return ModelsResponse(
            chat_models=[],
            embedding_models=[],
            ollama_status="unavailable",
        )

    chat: list[ModelInfo] = []
    embeds: list[ModelInfo] = []
    default_chat = settings.ollama_chat_model
    default_embed = settings.ollama_embed_model

    for item in raw:
        name = item.get("name") or item.get("model") or ""
        if not name:
            continue
        details = item.get("details") or {}
        info = ModelInfo(
            name=name,
            default=False,
            family=details.get("family"),
            parameter_size=details.get("parameter_size"),
        )
        if _is_embedding(name, details):
            info.default = name == default_embed or name.startswith(f"{default_embed}")
            embeds.append(info)
        else:
            info.default = name == default_chat or name.startswith(f"{default_chat}")
            chat.append(info)

    # Asegurar flags default aunque el nombre no coincida exacto
    if chat and not any(m.default for m in chat):
        for m in chat:
            if default_chat in m.name:
                m.default = True
                break
    if embeds and not any(m.default for m in embeds):
        for m in embeds:
            if default_embed in m.name:
                m.default = True
                break

    return ModelsResponse(
        chat_models=chat,
        embedding_models=embeds,
        ollama_status="available",
    )
