"""Cliente LLM delgado sobre la interfaz compatible con OpenAI de Ollama.

Por qué un wrapper propio y no usar el SDK de OpenAI directo en cada sitio:
- Punto único para cambiar de proveedor (Ollama -> LocalAI -> vLLM -> nube)
  sin tocar agentes/skills que consumen `LLMClient`.
- Punto único donde aplicar timeouts, reintentos y logging.

Implementación original.
"""

from openai import OpenAI

from core.config import get_settings


class LLMClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._chat_model = settings.ollama_chat_model
        self._embed_model = settings.ollama_embed_model
        self._client = OpenAI(
            base_url=settings.openai_compat_base_url,
            api_key="ollama-local-no-key-needed",
        )

    @property
    def default_chat_model(self) -> str:
        return self._chat_model

    @property
    def default_embed_model(self) -> str:
        return self._embed_model

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.2,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        kwargs: dict = {
            "model": model or self._chat_model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        response = self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        response = self._client.embeddings.create(
            model=model or self._embed_model,
            input=texts,
        )
        return [item.embedding for item in response.data]


_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client


def reset_llm_client() -> None:
    """Solo para tests: invalida el singleton."""
    global _client
    _client = None
