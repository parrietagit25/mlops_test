"""Construcción y validación de payloads de chat (contrato POST /chat).

Límites del Gateway (UI-0B) — sin truncado silencioso:
- roles: system | user | assistant
- content: 1..16000 chars, no blank
- messages: 1..40
- total chars <= 32000
- temperature: 0.0..1.5
- max_tokens: 1..2048

Si se supera un límite se lanza ValueError; la UI debe mostrar el error
y no enviar la solicitud.
"""

from __future__ import annotations

from typing import Any

MAX_MESSAGES = 40
MAX_CONTENT_LEN = 16_000
MAX_TOTAL_CHARS = 32_000
TEMP_MIN = 0.0
TEMP_MAX = 1.5
MAX_TOKENS_MIN = 1
MAX_TOKENS_MAX = 2048

LIMIT_EXCEEDED_MSG = (
    "La solicitud excede los límites permitidos. "
    "Limpia la conversación o acorta el mensaje / system prompt."
)


class ChatPayloadError(ValueError):
    """Error de validación de payload de chat."""


def validate_temperature(value: float) -> float:
    v = float(value)
    if v < TEMP_MIN or v > TEMP_MAX:
        raise ChatPayloadError(
            f"Temperature fuera de rango ({TEMP_MIN}–{TEMP_MAX})."
        )
    return v


def validate_max_tokens(value: int) -> int:
    v = int(value)
    if v < MAX_TOKENS_MIN or v > MAX_TOKENS_MAX:
        raise ChatPayloadError(
            f"Max tokens fuera de rango ({MAX_TOKENS_MIN}–{MAX_TOKENS_MAX})."
        )
    return v


def validate_content(text: str, *, field: str) -> str:
    content = (text or "").strip()
    if not content:
        raise ChatPayloadError(f"{field} no puede estar vacío.")
    if len(content) > MAX_CONTENT_LEN:
        raise ChatPayloadError(
            f"{field} supera el límite de {MAX_CONTENT_LEN} caracteres. {LIMIT_EXCEEDED_MSG}"
        )
    return content


def build_chat_payload(
    *,
    history: list[dict[str, Any]],
    user_text: str,
    system_prompt: str | None,
    model: str | None,
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    """Arma el body JSON para POST /chat.

    - Incluye system solo si no está vacío (una sola vez).
    - Incluye historial user/assistant en orden (sin metadata).
    - Incluye el mensaje nuevo del usuario.
    - No trunca ni modifica el contenido del usuario.
    """
    messages: list[dict[str, str]] = []

    raw_sys = (system_prompt or "").strip()
    if raw_sys:
        messages.append(
            {"role": "system", "content": validate_content(raw_sys, field="System prompt")}
        )

    for item in history:
        role = item.get("role")
        if role not in {"user", "assistant"}:
            continue
        raw = str(item.get("content") or "")
        if not raw.strip():
            continue
        # No modificar el contenido almacenado: solo validar límites.
        content = validate_content(raw, field="Un mensaje del historial")
        messages.append({"role": role, "content": content})

    user_content = validate_content(user_text, field="El mensaje")
    messages.append({"role": "user", "content": user_content})

    if len(messages) > MAX_MESSAGES:
        raise ChatPayloadError(
            f"La conversación supera el máximo de {MAX_MESSAGES} mensajes. "
            f"{LIMIT_EXCEEDED_MSG}"
        )

    total = sum(len(m["content"]) for m in messages)
    if total > MAX_TOTAL_CHARS:
        raise ChatPayloadError(
            f"La conversación supera el máximo de {MAX_TOTAL_CHARS} caracteres. "
            f"{LIMIT_EXCEEDED_MSG}"
        )

    if not model or not str(model).strip():
        raise ChatPayloadError("No hay un modelo seleccionado.")

    payload: dict[str, Any] = {
        "messages": messages,
        "model": str(model).strip(),
        "temperature": validate_temperature(temperature),
        "max_tokens": validate_max_tokens(max_tokens),
    }
    return payload


def select_default_chat_model(models_payload: dict[str, Any] | None) -> tuple[str | None, bool]:
    """Devuelve (nombre, used_fallback_without_default_flag)."""
    if not models_payload:
        return None, False
    chat_models = models_payload.get("chat_models") or []
    for item in chat_models:
        if item.get("default") and item.get("name"):
            return str(item["name"]), False
    names = [str(m["name"]) for m in chat_models if m.get("name")]
    if names:
        return names[0], True
    return None, False


def chat_model_names(models_payload: dict[str, Any] | None) -> list[str]:
    if not models_payload:
        return []
    return [str(m["name"]) for m in (models_payload.get("chat_models") or []) if m.get("name")]


def format_assistant_caption(metadata: dict[str, Any] | None) -> str:
    meta = metadata or {}
    model = meta.get("model") or "No disponible"
    duration = meta.get("duration_ms")
    if duration is None:
        duration_txt = "No disponible"
    else:
        try:
            duration_txt = f"{float(duration) / 1000.0:.2f} s"
        except (TypeError, ValueError):
            duration_txt = "No disponible"
    trace = meta.get("trace_id")
    trace_txt = str(trace) if trace else "no disponible"
    return f"Modelo: {model} · Duración: {duration_txt} · Trace: {trace_txt}"


def humanize_chat_error(
    *,
    error_kind: str | None,
    error_code: str | None,
    error_message: str | None,
    status_code: int | None,
) -> str:
    if error_kind == "connection":
        return "Gateway no disponible. Verifica que ailab-api esté activo."
    if error_kind == "timeout":
        return "La solicitud de chat superó el tiempo de espera."
    if error_kind == "unavailable" or status_code == 503:
        return "Ollama no está disponible temporalmente."
    if error_code == "MODEL_NOT_FOUND":
        return "El modelo seleccionado ya no está disponible. Actualiza la lista de modelos."
    if status_code == 422:
        return "La solicitud excede los límites permitidos o no pasó la validación."
    if status_code == 400:
        return error_message or "La solicitud fue rechazada por el Gateway."
    if status_code == 500 or error_kind == "server_error":
        return "Error interno del Gateway al generar la respuesta."
    if error_kind == "invalid_json":
        return "La respuesta del Gateway no tiene el formato esperado."
    return error_message or "No se pudo completar la solicitud de chat."
