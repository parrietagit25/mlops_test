"""Instrumentación de observabilidad hacia Arize Phoenix (OpenTelemetry/OTLP).

Patrón: auto-instrumentación del SDK de OpenAI vía OpenInference, exportando
al colector OTLP de Phoenix. Esto permite ver trazas de cada llamada al LLM
(prompt, respuesta, latencia, tokens) en http://localhost:6006 sin tener que
instrumentar manualmente cada request.

Implementación original; el patrón de "un solo register() al boot" es el
recomendado por la documentación pública de arize-ai/phoenix (Apache/ELv2,
ver docs/security-notes.md).
"""

from core.config import get_settings

_initialized = False


def setup_tracing() -> None:
    global _initialized
    if _initialized:
        return

    settings = get_settings()
    if not settings.enable_tracing:
        return

    try:
        from openinference.instrumentation.openai import OpenAIInstrumentor
        from phoenix.otel import register

        tracer_provider = register(
            project_name="ai-testing-lab",
            endpoint=settings.phoenix_collector_endpoint,
        )
        OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)
        _initialized = True
    except Exception as exc:  # pragma: no cover - la tracing nunca debe tumbar la API
        print(f"[tracing] No se pudo inicializar Phoenix ({exc}). Continuando sin trazas.")
