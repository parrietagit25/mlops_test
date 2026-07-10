"""Modelo "juez" local para DeepEval, apuntando a Ollama en vez de OpenAI.

Por qué: las métricas de DeepEval (AnswerRelevancy, Faithfulness, etc.) usan
un LLM como evaluador ("LLM-as-judge"). Por defecto DeepEval asume OpenAI de
pago; aquí se sobreescribe con DeepEvalBaseLLM para evaluar 100% en local y
sin costo, usando el mismo modelo Ollama que sirve el resto del laboratorio.

Nota honesta (ver docs/testing-playbook.md): un modelo pequeño (1B-3B) como
juez es menos confiable que GPT-4 como juez. Para Fase 1 esto es aceptable
porque el objetivo es tener el arnés funcionando sin costo; si se necesita
mayor confiabilidad de juicio, cambiar OLLAMA_CHAT_MODEL por un modelo local
más grande (ej. qwen2.5:7b) o, en Fase 2, usar un juez en la nube.

Implementación original sobre la interfaz pública DeepEvalBaseLLM.
"""

import os

from deepeval.models.base_model import DeepEvalBaseLLM
from openai import OpenAI


class OllamaJudgeModel(DeepEvalBaseLLM):
    def __init__(self, model: str | None = None, base_url: str | None = None):
        self.model_name = model or os.getenv("OLLAMA_CHAT_MODEL", "llama3.2:1b")
        base = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.client = OpenAI(base_url=f"{base.rstrip('/')}/v1", api_key="not-needed")
        super().__init__(self.model_name)

    def load_model(self):
        return self.client

    def generate(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        return response.choices[0].message.content or ""

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)

    def get_model_name(self) -> str:
        return f"ollama:{self.model_name}"
