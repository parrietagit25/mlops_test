# Atribuciones y licencias de terceros

`ai-testing-lab` es un proyecto original que **usa como dependencias**
(instaladas, no copiadas) las siguientes herramientas open source.
Ver también `docs/security-notes.md` para el análisis de qué implica cada
licencia y qué partes de este repo son originales vs. de terceros.

| Herramienta | Repositorio | Licencia | Cómo se usa aquí |
|---|---|---|---|
| Ollama | ollama/ollama | MIT | Servicio Docker (`ollama` en `docker-compose.yml`), sin modificar. |
| Arize Phoenix | Arize-ai/phoenix | Elastic License 2.0 | Servicio Docker (`phoenix`), sin modificar. |
| promptfoo | promptfoo/promptfoo | MIT | CLI invocada vía npx, con archivos de configuración propios (`evals/promptfoo/*`, `evals/security/promptfoo_redteam/*`). |
| DeepEval | confident-ai/deepeval | Apache-2.0 | Librería Python invocada desde `evals/deepeval/*` (código propio). |
| Ragas | explodinggradients/ragas | Apache-2.0 | Librería Python invocada desde `evals/ragas/evaluate_rag.py` (código propio). |
| garak | NVIDIA/garak | Apache-2.0 | CLI de terceros, uso documentado en `evals/security/garak/README.md`. |
| ModelScan | protectai/modelscan | Apache-2.0 | CLI de terceros, uso documentado en `evals/security/modelscan/README.md`. |
| openai (SDK Python) | openai/openai-python | Apache-2.0 | Cliente HTTP usado para hablar con la interfaz compatible de Ollama (`app/core/llm_client.py`). |
| FastAPI | fastapi/fastapi | MIT | Framework del gateway propio (`app/api/main.py`). |
| Pydantic | pydantic/pydantic | MIT | Tipado de settings y de payloads de skills. |

## Herramientas analizadas como referencia (no instaladas en la Fase 1)

Ver la clasificación completa con razones en `docs/architecture.md`,
sección 2. Resumen de licencias:

- **MIT**: LocalAI, Langfuse (core), llm-guard, LangGraph, CrewAI,
  pydantic-ai, agentevals, openevals, lm-evaluation-harness, openai/evals,
  openai/simple-evals.
- **Apache-2.0**: vLLM, BentoML, Ray, KServe, Giskard-oss, Giskard-skills,
  Opik, MLflow.
- **BSD-3-Clause**: Triton Inference Server.

Ninguno de estos repos fue copiado ni parcialmente incorporado a este
código. Donde se documenta "patrón" en `docs/architecture.md`, significa
que se leyó su enfoque conceptual (ej. contratos tipados de entrada/salida,
unidades de capacidad pequeñas) para diseñar algo propio, no que se haya
reutilizado su código fuente.

## Aviso

Verifica siempre el archivo `LICENSE` de la versión exacta que instales de
cada herramienta antes de un uso comercial o de redistribuir este
laboratorio — las licencias de proyectos open source pueden cambiar entre
versiones.
