"""Construcción y validación de payloads de Skills (UI-1C).

Contratos reales del Gateway (inspeccionados):

GET /skills → [{name, description}, ...]

POST /agents/{skill_name}/run
  body: { "payload": { ... } }
  200: { "output": str, "metadata": dict }
  404: SKILL_NOT_FOUND
  422: INVALID_PAYLOAD

summarizer (SummarizerInput):
  text: str, min_length=1
  max_sentences: int, default=3, ge=1, le=10

rag_qa (RagQAInput):
  question: str, min_length=1
  top_k: int, default=3, ge=1, le=10
"""

from __future__ import annotations

from typing import Any

# Skills que la UI-1C soporta visualmente (intersección obligatoria con GET /skills).
UI_SUPPORTED_SKILLS = frozenset({"summarizer", "rag_qa"})

SUMMARIZER_MAX_SENTENCES_MIN = 1
SUMMARIZER_MAX_SENTENCES_MAX = 10
SUMMARIZER_MAX_SENTENCES_DEFAULT = 3

RAG_TOP_K_MIN = 1
RAG_TOP_K_MAX = 10
RAG_TOP_K_DEFAULT = 3

# Límite de memoria en UI (el backend solo exige min_length=1).
UI_TEXT_MAX_LEN = 16_000

SKILLS_HISTORY_LIMIT = 20
SKILLS_HISTORY_SUMMARY_LEN = 120
SKILLS_HISTORY_OUTPUT_LEN = 2_000


class SkillPayloadError(ValueError):
    """Error de validación de payload de skill."""


def authorized_skill_names(skills_payload: list[dict[str, Any]] | None) -> list[str]:
    """Intersección ordenada: Gateway ∩ skills soportadas por la UI."""
    if not isinstance(skills_payload, list):
        return []
    names: list[str] = []
    for item in skills_payload:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if name in UI_SUPPORTED_SKILLS and name not in names:
            names.append(name)
    return names


def skill_description(
    skills_payload: list[dict[str, Any]] | None,
    skill_name: str,
) -> str:
    for item in skills_payload or []:
        if isinstance(item, dict) and item.get("name") == skill_name:
            desc = str(item.get("description") or "").strip()
            if desc:
                return desc
    return {
        "summarizer": "Resume un texto utilizando el modelo configurado en el Gateway.",
        "rag_qa": "Responde preguntas usando el índice RAG local vía el Agent Runtime.",
    }.get(skill_name, "")


def assert_skill_allowed(skill_name: str, available: list[str]) -> str:
    name = (skill_name or "").strip()
    if not name:
        raise SkillPayloadError("No hay una skill seleccionada.")
    if name not in UI_SUPPORTED_SKILLS:
        raise SkillPayloadError("Skill no autorizada en esta interfaz.")
    if name not in available:
        raise SkillPayloadError(
            "La skill seleccionada ya no está disponible. Actualiza la lista."
        )
    return name


def build_summarizer_payload(*, text: str, max_sentences: int) -> dict[str, Any]:
    content = (text or "").strip()
    if not content:
        raise SkillPayloadError("El texto a resumir no puede estar vacío.")
    if len(content) > UI_TEXT_MAX_LEN:
        raise SkillPayloadError(
            f"El texto supera el límite de {UI_TEXT_MAX_LEN} caracteres."
        )
    n = int(max_sentences)
    if n < SUMMARIZER_MAX_SENTENCES_MIN or n > SUMMARIZER_MAX_SENTENCES_MAX:
        raise SkillPayloadError(
            f"max_sentences debe estar entre {SUMMARIZER_MAX_SENTENCES_MIN} y "
            f"{SUMMARIZER_MAX_SENTENCES_MAX}."
        )
    # Solo campos del contrato SummarizerInput.
    return {"text": content, "max_sentences": n}


def build_rag_qa_payload(*, question: str, top_k: int) -> dict[str, Any]:
    q = (question or "").strip()
    if not q:
        raise SkillPayloadError("La pregunta no puede estar vacía.")
    if len(q) > UI_TEXT_MAX_LEN:
        raise SkillPayloadError(
            f"La pregunta supera el límite de {UI_TEXT_MAX_LEN} caracteres."
        )
    k = int(top_k)
    if k < RAG_TOP_K_MIN or k > RAG_TOP_K_MAX:
        raise SkillPayloadError(
            f"top_k debe estar entre {RAG_TOP_K_MIN} y {RAG_TOP_K_MAX}."
        )
    # Solo campos del contrato RagQAInput.
    return {"question": q, "top_k": k}


def build_skill_payload(skill_name: str, form_values: dict[str, Any]) -> dict[str, Any]:
    if skill_name == "summarizer":
        return build_summarizer_payload(
            text=str(form_values.get("text") or ""),
            max_sentences=int(form_values.get("max_sentences") or SUMMARIZER_MAX_SENTENCES_DEFAULT),
        )
    if skill_name == "rag_qa":
        return build_rag_qa_payload(
            question=str(form_values.get("question") or ""),
            top_k=int(form_values.get("top_k") or RAG_TOP_K_DEFAULT),
        )
    raise SkillPayloadError("Skill no autorizada en esta interfaz.")


def summarize_input(skill_name: str, payload: dict[str, Any]) -> str:
    if skill_name == "summarizer":
        raw = str(payload.get("text") or "")
    elif skill_name == "rag_qa":
        raw = str(payload.get("question") or "")
    else:
        raw = ""
    raw = " ".join(raw.split())
    if len(raw) > SKILLS_HISTORY_SUMMARY_LEN:
        return raw[: SKILLS_HISTORY_SUMMARY_LEN - 3] + "..."
    return raw


def truncate_output(output: str) -> str:
    text = str(output or "")
    if len(text) > SKILLS_HISTORY_OUTPUT_LEN:
        return text[: SKILLS_HISTORY_OUTPUT_LEN - 3] + "..."
    return text


def parse_skill_result(data: Any) -> tuple[str | None, dict[str, Any] | None, str | None]:
    """Devuelve (output, metadata, error_message)."""
    if not isinstance(data, dict):
        return None, None, "La respuesta del Gateway no tiene el formato esperado."
    output = data.get("output")
    if output is None or str(output).strip() == "":
        return None, None, "La respuesta del Gateway no tiene el formato esperado."
    meta = data.get("metadata")
    if meta is not None and not isinstance(meta, dict):
        meta = {}
    return str(output), (meta or {}), None


def humanize_skill_error(
    *,
    error_kind: str | None,
    error_code: str | None,
    error_message: str | None,
    status_code: int | None,
) -> str:
    if error_kind == "connection":
        return "Gateway no disponible. Verifica que ailab-api esté activo."
    if error_kind == "timeout":
        return "La ejecución de la skill superó el tiempo de espera."
    if error_kind == "unavailable" or status_code == 503:
        return "Ollama u otro servicio requerido no está disponible temporalmente."
    if error_code == "SKILL_NOT_FOUND" or status_code == 404:
        return "La skill solicitada no existe o ya no está registrada."
    if error_code == "INVALID_PAYLOAD" or status_code == 422:
        return "El payload no es válido para esta skill."
    if status_code == 400:
        return error_message or "La solicitud fue rechazada por el Gateway."
    if status_code == 500 or error_kind == "server_error":
        return "Error interno del Gateway al ejecutar la skill."
    if error_kind == "invalid_json":
        return "La respuesta del Gateway no tiene el formato esperado."
    return error_message or "No se pudo completar la ejecución de la skill."


def safe_metadata_for_display(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Filtra metadata a campos no sensibles conocidos."""
    meta = metadata or {}
    allowed = {}
    if "skill" in meta and meta["skill"] is not None:
        allowed["skill"] = str(meta["skill"])
    if "chunks_used" in meta and meta["chunks_used"] is not None:
        try:
            allowed["chunks_used"] = int(meta["chunks_used"])
        except (TypeError, ValueError):
            pass
    if "sources" in meta and isinstance(meta["sources"], list):
        # Solo nombres de fuente (ya son relativos en el contrato), sin rutas.
        sources = [str(s) for s in meta["sources"] if s is not None][:10]
        if sources:
            allowed["sources"] = sources
    return allowed
