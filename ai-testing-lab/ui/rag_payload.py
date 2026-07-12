"""Validación y presentación RAG (UI-1D) — alineado a contratos reales del Gateway.

GET /rag/status → RagStatusResponse
POST /rag/ingest → multipart field `files` (opcional); sin files = sample_docs
GET /rag/query?q=&top_k= → {query, results:[{source,text,score}]}

Límites Gateway (Settings):
- extensiones: .txt, .md
- max upload: 512_000 bytes
- max files: 10
"""

from __future__ import annotations

from typing import Any

ALLOWED_EXTENSIONS = frozenset({".txt", ".md"})
BLOCKED_EXTENSIONS = frozenset(
    {".py", ".sh", ".ps1", ".exe", ".zip", ".pdf", ".docx", ".bin", ".gz", ".tar"}
)
MAX_UPLOAD_BYTES = 512_000
MAX_FILES_PER_REQUEST = 10
QUERY_TOP_K_MIN = 1
QUERY_TOP_K_MAX = 10
QUERY_TOP_K_DEFAULT = 3
QUERY_MAX_LEN = 16_000
CHUNK_TEXT_DISPLAY_MAX = 2_000
HISTORY_LIMIT = 20
HISTORY_SUMMARY_LEN = 120


class RagPayloadError(ValueError):
    """Error de validación local de RAG (UI)."""


def unique_sources(results: list[dict[str, Any]] | None) -> list[str]:
    """Fuentes únicas en orden de primera aparición (solo presentación)."""
    seen: set[str] = set()
    ordered: list[str] = []
    for item in results or []:
        if not isinstance(item, dict):
            continue
        src = item.get("source")
        if src is None:
            continue
        name = str(src).strip()
        if not name or name in seen:
            continue
        # No mostrar rutas: solo basename lógico.
        if "/" in name or "\\" in name:
            name = name.replace("\\", "/").rsplit("/", 1)[-1]
        if name in seen:
            continue
        seen.add(name)
        ordered.append(name)
    return ordered


def validate_upload_filename(filename: str) -> str:
    name = (filename or "").strip()
    if not name:
        raise RagPayloadError("Nombre de archivo vacío.")
    if ".." in name or "/" in name or "\\" in name or name.startswith("~"):
        raise RagPayloadError("Nombre de archivo no permitido (ruta o path traversal).")
    if ":" in name and len(name) > 2 and name[1] == ":":
        raise RagPayloadError("Nombre de archivo absoluto no permitido.")
    lower = name.lower()
    ext = ""
    for allowed in ALLOWED_EXTENSIONS:
        if lower.endswith(allowed):
            ext = allowed
            break
    if not ext:
        for blocked in BLOCKED_EXTENSIONS:
            if lower.endswith(blocked):
                raise RagPayloadError(
                    f"Extensión no permitida ({blocked}). Solo .txt y .md."
                )
        raise RagPayloadError("Extensión no permitida. Solo .txt y .md.")
    return name


def validate_upload_file(*, filename: str, size: int) -> str:
    safe = validate_upload_filename(filename)
    if size is None or int(size) <= 0:
        raise RagPayloadError(f"El archivo '{safe}' está vacío.")
    if int(size) > MAX_UPLOAD_BYTES:
        raise RagPayloadError(
            f"El archivo '{safe}' supera el límite de {MAX_UPLOAD_BYTES} bytes."
        )
    return safe


def validate_upload_batch(files: list[tuple[str, int]]) -> list[str]:
    if not files:
        raise RagPayloadError("Selecciona al menos un archivo para ingerir.")
    if len(files) > MAX_FILES_PER_REQUEST:
        raise RagPayloadError(
            f"Máximo {MAX_FILES_PER_REQUEST} archivos por solicitud."
        )
    return [validate_upload_file(filename=n, size=s) for n, s in files]


def upload_selection_error(files: list[tuple[str, int]]) -> str | None:
    """Devuelve mensaje de error o None si la selección es válida para enviar."""
    try:
        validate_upload_batch(files)
    except RagPayloadError as exc:
        return str(exc)
    return None


def validate_query(*, question: str, top_k: int) -> tuple[str, int]:
    q = (question or "").strip()
    if not q:
        raise RagPayloadError("La pregunta no puede estar vacía.")
    if len(q) > QUERY_MAX_LEN:
        raise RagPayloadError(
            f"La pregunta supera el límite de {QUERY_MAX_LEN} caracteres."
        )
    k = int(top_k)
    if k < QUERY_TOP_K_MIN or k > QUERY_TOP_K_MAX:
        raise RagPayloadError(
            f"top_k debe estar entre {QUERY_TOP_K_MIN} y {QUERY_TOP_K_MAX}."
        )
    return q, k


def truncate_text(text: str, max_len: int = CHUNK_TEXT_DISPLAY_MAX) -> str:
    raw = str(text or "")
    if len(raw) <= max_len:
        return raw
    return raw[: max_len - 3] + "..."


def summarize_question(question: str) -> str:
    raw = " ".join(str(question or "").split())
    if len(raw) > HISTORY_SUMMARY_LEN:
        return raw[: HISTORY_SUMMARY_LEN - 3] + "..."
    return raw


def parse_query_response(data: Any) -> tuple[str | None, list[dict[str, Any]], str | None]:
    """Devuelve (query, results, error)."""
    if not isinstance(data, dict):
        return None, [], "La respuesta del Gateway no tiene el formato esperado."
    query = data.get("query")
    results = data.get("results")
    if results is None:
        return None, [], "La respuesta del Gateway no tiene el formato esperado."
    if not isinstance(results, list):
        return None, [], "La respuesta del Gateway no tiene el formato esperado."
    cleaned: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        entry: dict[str, Any] = {
            "source": str(item.get("source") or "desconocido"),
            "text": str(item.get("text") or ""),
        }
        if "score" in item and item["score"] is not None:
            try:
                entry["score"] = float(item["score"])
            except (TypeError, ValueError):
                pass
        cleaned.append(entry)
    return (str(query) if query is not None else None), cleaned, None


def safe_status_fields(data: dict[str, Any] | None) -> dict[str, Any]:
    """Campos seguros de GET /rag/status (sin rutas host)."""
    if not isinstance(data, dict):
        return {}
    out: dict[str, Any] = {}
    for key in (
        "available",
        "embedding_model",
        "documents_indexed",
        "chunks_indexed",
        "allowed_extensions",
        "last_ingest_at",
        "warning",
        "uploads_enabled",
        "allowed_directory",
    ):
        if key in data and data[key] is not None:
            out[key] = data[key]
    # allowed_directory es lógico relativo; no es ruta host absoluta.
    return out


def humanize_rag_error(
    *,
    error_kind: str | None,
    error_code: str | None,
    error_message: str | None,
    status_code: int | None,
) -> str:
    if error_kind == "connection":
        return "Gateway no disponible. Verifica que ailab-api esté activo."
    if error_kind == "timeout":
        return "La operación RAG superó el tiempo de espera."
    if error_kind == "unavailable" or status_code == 503:
        return "Ollama o el servicio de embeddings no está disponible temporalmente."
    if error_code in {"FILE_TOO_LARGE", "TOO_MANY_FILES"} or status_code == 413:
        return error_message or "Archivo demasiado grande o demasiados archivos."
    if error_code in {"INVALID_FILENAME", "INVALID_UPLOAD", "EMPTY_FILE"} or status_code == 400:
        return error_message or "Archivo o solicitud no permitidos."
    if status_code == 404:
        return "Recurso RAG no encontrado."
    if status_code == 422:
        return "La solicitud RAG no pasó la validación."
    if status_code == 500 or error_kind == "server_error":
        return "Error interno del Gateway al procesar RAG."
    if error_kind == "invalid_json":
        return "La respuesta del Gateway no tiene el formato esperado."
    return error_message or "No se pudo completar la operación RAG."
