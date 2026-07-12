"""Sanitización de nombres de archivo para uploads controlados."""

from __future__ import annotations

import re
from pathlib import PurePosixPath, PureWindowsPath

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class UnsafeFilenameError(ValueError):
    """Nombre de archivo rechazado por política de seguridad."""


def sanitize_filename(name: str, allowed_extensions: set[str]) -> str:
    """Devuelve un basename seguro con extensión permitida en minúsculas.

    Rechaza rutas, `..`, nombres vacíos y extensiones fuera de la whitelist.
    """
    if not name or not name.strip():
        raise UnsafeFilenameError("Nombre de archivo vacío.")

    raw = name.strip().replace("\x00", "")
    # Rechazar path traversal / separadores en la entrada original (antes de basename).
    if ".." in raw or "/" in raw or "\\" in raw or raw.startswith("~"):
        raise UnsafeFilenameError("Path traversal detectado en el nombre.")

    # Tomar solo el basename en ambos estilos de separador (defensa en profundidad).
    base = PureWindowsPath(raw).name
    base = PurePosixPath(base).name
    if not base or base in {".", ".."}:
        raise UnsafeFilenameError("Nombre de archivo inválido.")
    if "/" in base or "\\" in base or ".." in base:
        raise UnsafeFilenameError("Path traversal detectado en el nombre.")

    lower = base.lower()
    ext = ""
    for allowed in allowed_extensions:
        if lower.endswith(allowed):
            ext = allowed
            break
    if not ext:
        raise UnsafeFilenameError(
            f"Extensión no permitida. Solo: {', '.join(sorted(allowed_extensions))}"
        )

    stem = base[: -len(ext)]
    stem = _SAFE_NAME.sub("_", stem).strip("._") or "document"
    stem = stem[:120]
    return f"{stem}{ext}"
