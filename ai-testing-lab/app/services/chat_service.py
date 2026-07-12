"""Servicio de chat: reutiliza LLMClient; no acepta URLs de proveedor."""

from __future__ import annotations

import time
from typing import Any

from openai import APIConnectionError, APIStatusError, NotFoundError

from core.llm_client import get_llm_client
from schemas.chat import ChatRequest, ChatResponse
from services.ollama_probe import OllamaUnavailableError, list_ollama_tags, probe_ollama


def _current_trace_id() -> str | None:
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx is not None and getattr(ctx, "is_valid", False):
            return format(ctx.trace_id, "032x")
    except Exception:
        return None
    return None


def run_chat(request: ChatRequest) -> ChatResponse:
    if not probe_ollama():
        raise OllamaUnavailableError("Ollama no está disponible.")

    llm = get_llm_client()
    model = request.model or llm.default_chat_model

    # Validar existencia del modelo cuando Ollama responde.
    try:
        tags = list_ollama_tags()
        names = {m.get("name") or m.get("model") for m in tags}
        # Ollama a veces lista "llama3.2:1b" y también con :latest
        aliases = set(names)
        for n in list(names):
            if n and ":" not in n:
                aliases.add(f"{n}:latest")
            if n and n.endswith(":latest"):
                aliases.add(n.removesuffix(":latest"))
        if model not in aliases and f"{model}:latest" not in aliases:
            raise LookupError(f"Modelo no encontrado en Ollama: {model}")
    except OllamaUnavailableError:
        raise
    except LookupError:
        raise

    messages: list[dict[str, Any]] = [
        {"role": m.role, "content": m.content} for m in request.messages
    ]

    started = time.perf_counter()
    try:
        reply = llm.chat(
            messages=messages,
            temperature=request.temperature,
            model=model,
            max_tokens=request.max_tokens,
        )
    except (APIConnectionError, APIStatusError) as exc:
        raise OllamaUnavailableError(f"Error al llamar al modelo: {exc}") from exc
    except NotFoundError as exc:
        raise LookupError(f"Modelo no encontrado: {model}") from exc

    duration_ms = (time.perf_counter() - started) * 1000.0
    return ChatResponse(
        reply=reply,
        model=model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        duration_ms=round(duration_ms, 2),
        trace_id=_current_trace_id(),
    )
