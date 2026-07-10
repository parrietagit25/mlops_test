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

    def chat(self, messages: list[dict], temperature: float = 0.2, model: str | None = None) -> str:
        response = self._client.chat.completions.create(
            model=model or self._chat_model,
            messages=messages,
            temperature=temperature,
        )
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
