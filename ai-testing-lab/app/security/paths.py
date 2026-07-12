"""Path jail: garantizar que rutas resueltas permanecen bajo un directorio raíz."""

from __future__ import annotations

from pathlib import Path


class PathJailError(ValueError):
    """La ruta solicitada escapa del directorio permitido."""


def resolve_under(root: Path, *parts: str) -> Path:
    """Resuelve `root/parts` y verifica que el resultado quede dentro de `root`.

    Rechaza componentes vacíos, `.`, `..`, separadores absolutos y rutas que
    tras `resolve()` queden fuera del jail.
    """
    root_resolved = root.resolve()
    for part in parts:
        if not part or part in {".", ".."}:
            raise PathJailError("Componente de ruta no permitido.")
        if "/" in part or "\\" in part:
            raise PathJailError("No se permiten separadores en componentes de ruta.")
        if ":" in part:
            raise PathJailError("No se permiten rutas con drive/UNC.")

    candidate = root_resolved.joinpath(*parts).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise PathJailError("La ruta escapa del directorio permitido.") from exc
    return candidate


def is_within(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False
