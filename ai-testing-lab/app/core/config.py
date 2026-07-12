"""Configuración central de la aplicación, cargada desde variables de entorno.

Implementación original. Patrón de settings basado en pydantic-settings
(estándar en el ecosistema FastAPI), no copiado de ningún repo de referencia.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_lab_root() -> str:
    """Raíz del laboratorio: LAB_ROOT o el padre de `app/`."""
    # app/core/config.py → parents[2] = ai-testing-lab/
    return str(Path(__file__).resolve().parents[2])


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Model serving
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.2:1b"
    ollama_embed_model: str = "nomic-embed-text"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8080

    # Observabilidad
    phoenix_collector_endpoint: str = "http://localhost:4317"
    # URL para la UI / enlaces en el cliente (navegador en el host).
    phoenix_ui_url: str = "http://127.0.0.1:6006"
    # URL para sondas server-side (en Compose: http://phoenix:6006).
    phoenix_probe_url: str | None = None
    enable_tracing: bool = True

    # Lab root (scripts/, evals/, reports/)
    lab_root: str = Field(default_factory=_default_lab_root)

    # RAG
    rag_index_path: str = "rag/.index/index.json"
    rag_top_k: int = 3
    rag_chunk_size: int = 500
    rag_chunk_overlap: int = 50
    rag_uploads_dir: str = "rag/uploads"
    rag_max_upload_bytes: int = 512_000
    rag_max_files_per_request: int = 10

    # Evals / jobs (Fase 1: in-memory)
    eval_timeout_seconds: int = 1800
    eval_output_max_chars: int = 20_000

    # Reports
    reports_max_list: int = 50
    reports_max_file_bytes: int = 1_000_000

    log_level: str = "info"
    environment: str = "local"

    @property
    def openai_compat_base_url(self) -> str:
        """Ollama expone una interfaz compatible con la API de OpenAI en /v1."""
        return f"{self.ollama_base_url.rstrip('/')}/v1"

    @property
    def phoenix_health_url(self) -> str:
        return (self.phoenix_probe_url or self.phoenix_ui_url).rstrip("/")

    @property
    def lab_root_path(self) -> Path:
        return Path(self.lab_root).resolve()

    @property
    def reports_dir(self) -> Path:
        return self.lab_root_path / "reports"

    @property
    def rag_allowed_extensions(self) -> set[str]:
        return {".txt", ".md"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
