"""Carga simple de plantillas de prompt desde app/prompts/templates/*.txt.

Las plantillas usan `str.format(**kwargs)` (placeholders tipo {variable}).
Se evita a propósito una dependencia de templating pesada (Jinja2) para
mantener la Fase 1 minimalista; si el laboratorio crece, este es el punto
de extensión natural.
"""

from pathlib import Path

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def load_prompt(name: str, **kwargs) -> str:
    path = _TEMPLATES_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template no encontrado: {path}")
    template = path.read_text(encoding="utf-8")
    return template.format(**kwargs)
