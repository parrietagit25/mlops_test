"""Uploads controlados para RAG (solo .txt/.md, path jail, sin ejecución)."""

from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile

from core.config import get_settings
from security.filenames import UnsafeFilenameError, sanitize_filename


class RagUploadError(ValueError):
    def __init__(self, message: str, code: str = "INVALID_UPLOAD") -> None:
        super().__init__(message)
        self.code = code


async def save_uploads(files: list[UploadFile]) -> list[str]:
    """Guarda archivos validados bajo app/rag/uploads/ y devuelve basenames."""
    settings = get_settings()
    if len(files) > settings.rag_max_files_per_request:
        raise RagUploadError(
            f"Máximo {settings.rag_max_files_per_request} archivos por solicitud.",
            code="TOO_MANY_FILES",
        )

    upload_dir = Path(__file__).resolve().parents[1] / "rag" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    # Evitar que alguien deje ejecutables previos: solo tocamos basenames sanitizados.

    saved: list[str] = []
    for upload in files:
        original = upload.filename or ""
        try:
            safe_name = sanitize_filename(original, settings.rag_allowed_extensions)
        except UnsafeFilenameError as exc:
            raise RagUploadError(str(exc), code="INVALID_FILENAME") from exc

        data = await upload.read()
        if len(data) > settings.rag_max_upload_bytes:
            raise RagUploadError(
                f"Archivo '{safe_name}' excede el límite de "
                f"{settings.rag_max_upload_bytes} bytes.",
                code="FILE_TOO_LARGE",
            )
        if not data:
            raise RagUploadError(f"Archivo '{safe_name}' vacío.", code="EMPTY_FILE")

        # No ejecutar: solo escritura binaria/texto.
        dest = upload_dir / safe_name
        dest.write_bytes(data)
        saved.append(safe_name)

    return saved
