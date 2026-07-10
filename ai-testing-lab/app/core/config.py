"""Configuración central de la aplicación, cargada desde variables de entorno.

Implementación original. Patrón de settings basado en pydantic-settings
(estándar en el ecosistema FastAPI), no copiado de ningún repo de referencia.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    enable_tracing: bool = True

    # RAG
    rag_index_path: str = "rag/.index/index.json"
    rag_top_k: int = 3
    rag_chunk_size: int = 500
    rag_chunk_overlap: int = 50

    log_level: str = "info"
    environment: str = "local"

    @property
    def openai_compat_base_url(self) -> str:
        """Ollama expone una interfaz compatible con la API de OpenAI en /v1."""
        return f"{self.ollama_base_url.rstrip('/')}/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
