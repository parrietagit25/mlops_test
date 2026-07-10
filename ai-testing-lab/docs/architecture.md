# Arquitectura de ai-testing-lab

## 1. Resumen ejecutivo

`ai-testing-lab` es un laboratorio personal, 100% local y sin costo, para
probar modelos de IA, prompts, agentes/skills y pipelines RAG, con
evaluación automatizada (calidad, RAG, seguridad) y observabilidad de
trazas. Está diseñado para escalar en una Fase 2 a una arquitectura
portable multi-cloud (DigitalOcean, AWS, Azure) sin rehacer el diseño base.

**Por qué esta arquitectura:** el requisito central es "cero costo, todo
local, pero real" — no un scaffold de juguete. Por eso cada pieza es una
herramienta open source ampliamente usada en su categoría (no una
reimplementación propia de evals/observabilidad/red teaming), conectada por
un gateway de API propio y minimalista que sí es implementación original.

**Por qué estas herramientas:** cada elección resuelve una necesidad
concreta del enunciado (servir modelos, testear prompts, testear la app,
evaluar RAG, red teaming, observabilidad, agentes) con la opción más
liviana dentro de su categoría que sigue siendo representativa de cómo se
hace en la industria (ver sección 2, clasificación completa).

---

## 2. Clasificación de repositorios de referencia (Paso 1)

Repos analizados, agrupados por función real dentro de este proyecto (no
por su descripción de marketing). "Uso" indica qué se hizo con cada uno:
**usado tal cual** (instalado/invocado como herramienta de terceros),
**patrón** (se leyó su enfoque conceptual y se reimplementó algo propio,
sin copiar código) o **Fase 2 / fuera de alcance** (documentado, no
implementado ahora, con la razón).

### Testing de prompts y modelos
| Repo | Licencia | Uso en ai-testing-lab | Por qué |
|---|---|---|---|
| promptfoo/promptfoo | MIT | **Usado tal cual** (Fase 1) | CLI probada, config declarativa YAML, soporta providers Ollama nativos y red teaming integrado. Cubre 2 requisitos del enunciado a la vez. |
| EleutherAI/lm-evaluation-harness | MIT | Fuera de alcance (Fase 1) | Orientado a benchmarks académicos de modelos base (MMLU, etc.), no a testear prompts/apps propias. No aporta al caso de uso actual. |
| openai/evals | MIT | Fuera de alcance (Fase 1) | Framework de evals estilo benchmark, redundante con promptfoo+deepeval para este alcance; más pesado de configurar. |
| openai/simple-evals | MIT | Fuera de alcance (Fase 1) | Enfocado en reproducir benchmarks públicos contra APIs; no es el caso de uso ("testear mis prompts/mi app"). |

### Testing de aplicaciones LLM y RAG
| Repo | Licencia | Uso | Por qué |
|---|---|---|---|
| confident-ai/deepeval | Apache-2.0 | **Usado tal cual** (Fase 1) | Estilo "pytest" para LLM apps, métricas (faithfulness, relevancy) con soporte de modelo evaluador custom (permite juez 100% local). |
| explodinggradients/ragas | Apache-2.0 | **Usado tal cual** (Fase 1) | Métricas estándar de facto para RAG (faithfulness, answer relevancy, context precision/recall), también soporta LLM evaluador custom. |
| Giskard-AI/giskard-oss | Apache-2.0 | Fase 2 (opcional) | Scanner automático de vulnerabilidades de modelo/LLM (bias, robustez). Muy útil, pero se solapa con DeepEval + promptfoo redteam para el MVP; añadirlo ahora triplica herramientas de la misma categoría sin necesidad real. |
| Giskard-AI/giskard-skills | Apache-2.0 | **Patrón** | Se tomó la idea conceptual de "unidades de capacidad pequeñas y testeables" para diseñar `app/agents/skills/`. No se copió código. |
| langchain-ai/agentevals | MIT | Fase 2 | Evalúa trayectorias de agentes multi-paso. Los skills actuales son de un solo paso; tiene sentido cuando haya agentes con planificación/loops reales. |
| langchain-ai/openevals | MIT | Fase 2 | "LLM-as-judge" reutilizable para respuestas de agentes; redundante con deepeval/ragas en el alcance actual. |

### Model serving local / compatible con OpenAI
| Repo | Licencia | Uso | Por qué |
|---|---|---|---|
| ollama/ollama | MIT | **Usado tal cual** (Fase 1, elegido) | Instalación trivial, catálogo curado de modelos, servidor `/v1` compatible con OpenAI, corre bien en CPU/laptop. |
| mudler/LocalAI | MIT | Documentado, no instalado | Alternativa compatible con OpenAI con más backends (audio, imagen, más formatos). Queda como reemplazo directo de `OLLAMA_BASE_URL` si Ollama no soporta un modelo/formato que necesites. |
| vllm-project/vllm | Apache-2.0 | Fase 2 (nube con GPU) | Altísimo throughput con paralelismo/batching continuo, pero requiere GPU para brillar; overkill/no rinde igual en CPU de laptop. Documentado para Fase 2A/2B con GPU en la nube. |

### Empaquetado / despliegue / serving a escala
| Repo | Licencia | Uso | Por qué |
|---|---|---|---|
| bentoml/BentoML | Apache-2.0 | Fase 2 (opcional) | Empaquetar modelos propios (fine-tunes) como microservicio versionado. Sin modelos propios entrenados aún, no aplica en Fase 1. |
| ray-project/ray | Apache-2.0 | Fase 2/3 | Cómputo distribuido para evals/entrenamiento a gran escala. Muy pesado para un laptop; solo se justifica con volumen real. |
| triton-inference-server/server | BSD-3-Clause | Fuera de alcance | Serving GPU multi-framework de NVIDIA orientado a producción a escala; no aporta nada en un laboratorio local de un solo usuario. |
| kserve/kserve | Apache-2.0 | Fase 2C | Serving de modelos sobre Kubernetes. Solo tiene sentido con un clúster K8s administrado real (ver `docs/phase-2-multicloud.md`). |

### Observabilidad
| Repo | Licencia | Uso | Por qué |
|---|---|---|---|
| arize-ai/phoenix | Elastic License 2.0 (ELv2) | **Usado tal cual** (Fase 1, elegido) | Un solo contenedor, OTel/OpenInference nativo, sin DB externa obligatoria. El más simple de desplegar de esta categoría. |
| langfuse/langfuse | MIT (open core; features Enterprise bajo licencia comercial aparte) | Fase 2 (alternativa fuerte) | Excelente gestión de prompts/datasets/evals online, pero su arquitectura de referencia (Postgres+ClickHouse+Redis+S3) es sobre-ingeniería para un laboratorio de una persona. Documentado como upgrade si se necesita gestión de prompts colaborativa. |
| comet-ml/opik | Apache-2.0 | Fase 2 (a comparar) | Alternativa moderna (trazas+evals+datasets) con licencia más permisiva que Phoenix. Buen candidato a re-evaluar en Fase 2 si ELv2 de Phoenix resulta un problema real. |
| mlflow/mlflow | Apache-2.0 | Fase 2 (complementario) | Tracking de experimentos/artefactos/registry de modelos clásico de ML. Útil cuando haya fine-tunes o modelos propios que versionar; no reemplaza trazas de LLM. |

### Seguridad / red teaming
| Repo | Licencia | Uso | Por qué |
|---|---|---|---|
| NVIDIA/garak | Apache-2.0 | **Usado tal cual** (Fase 1, bajo demanda) | Scanner de vulnerabilidades LLM (jailbreak, leakage, toxicidad) con generador nativo compatible con OpenAI. |
| protectai/modelscan | Apache-2.0 | **Usado tal cual** (Fase 1, bajo demanda) | Detecta código malicioso en artefactos serializados (pickle/torch/H5). Aplica cuando se descargan checkpoints manualmente, no a los modelos GGUF de `ollama pull`. |
| protectai/llm-guard | MIT | Fase 1.5 / 2 (próximo paso natural) | Guardrails de runtime (redacción de PII, detección de prompt injection, filtro de toxicidad) como middleware de la API. No se integró en el MVP para mantenerlo mínimo; es el paso lógico siguiente después de *detectar* vulnerabilidades con garak/redteam hacia *bloquearlas* en producción. |
| promptfoo/modelaudit | MIT | **Usado tal cual** (vía promptfoo) | Sus capacidades de auditoría/red teaming ya se cubren con la sección `redteam:` de la config de promptfoo (`evals/security/promptfoo_redteam/`), sin añadir una herramienta separada. |

### Frameworks de agentes
| Repo | Licencia | Uso | Por qué |
|---|---|---|---|
| langchain-ai/langgraph | MIT | **Patrón** / Fase 2 | Orquestación de agentes como grafos de estado con checkpointing. Se documenta como el upgrade natural de `app/agents/runtime.py` cuando los skills necesiten encadenarse con estado/branching. No se instaló el framework para el MVP de 2 skills de un solo paso. |
| crewAIInc/crewAI | MIT | Fase 2 (opcional) | Orquestación de agentes "por roles". Añade una capa de abstracción de alto nivel que no hace falta con 2 skills; interesante para prototipar escenarios multi-agente más adelante. |
| pydantic/pydantic-ai | MIT | **Patrón** | Se adoptó su idea de tipar estrictamente entrada/salida de cada capacidad con Pydantic (`Skill.input_model` en `app/agents/skills/base.py`), sin instalar el framework completo. |
| pydantic/pydantic-ai-harness | MIT (variante de pydantic-ai) | Fuera de alcance | Variante/experimental de pydantic-ai; mismo criterio que la fila anterior — se toma el patrón de tipado, no la dependencia. |

---

## 3. Stack elegido para Fase 1 (Paso 2)

| Necesidad | Elegido | Alternativa dejada fuera (por qué) |
|---|---|---|
| Servir modelos local | **Ollama** | LocalAI (más flexible pero más setup), vLLM (necesita GPU para brillar) |
| Testing de prompts | **promptfoo** | — (es la opción natural, MIT, cero fricción) |
| Testing de app LLM | **DeepEval** | Giskard-oss (se solapa, más pesado para el MVP) |
| Evaluación RAG | **Ragas** | — (estándar de facto, sin alternativa mejor en esta categoría) |
| Red teaming | **promptfoo redteam + garak** | Giskard-oss redteam (redundante con lo anterior) |
| Escaneo de artefactos | **ModelScan** | — (única opción seria en esta categoría específica) |
| Observabilidad | **Arize Phoenix** | Langfuse (más completo pero mucho más pesado en infra) |
| Agentes/skills | **Runtime propio + patrón pydantic-ai/Giskard-skills** | LangGraph/CrewAI (over-engineering para 2 skills de un paso) |
| API gateway | **FastAPI propio** | — (implementación original, necesaria como punto único de integración) |

Todo corre con **Docker Compose** (3 contenedores: `ollama`, `api`,
`phoenix`) más herramientas CLI de terceros (promptfoo, DeepEval, Ragas,
garak, ModelScan) que se instalan bajo demanda en el host o en entornos
virtuales dedicados — no se metieron todas dentro de la imagen de la API
para no acoplar el runtime de producción del laboratorio con las
dependencias (a veces pesadas) de las herramientas de evaluación.

**Qué se dejó fuera deliberadamente y por qué:** ver la columna "Fase 2 /
fuera de alcance" de la tabla de la sección 2. En resumen: todo lo que
requiere GPU real (vLLM, Triton), todo lo que requiere un clúster (KServe,
Ray a escala), y todo lo que duplicaría una categoría ya cubierta
(Giskard-oss vs. DeepEval+promptfoo, Langfuse vs. Phoenix, LangGraph/CrewAI
vs. runtime propio de 2 skills).

---

## 4. Arquitectura Fase 1

### 4.1 Componentes

- **Ollama** — sirve el modelo de chat y el modelo de embeddings, expone
  `/api` nativo y `/v1` compatible con OpenAI.
- **API (FastAPI, `app/`)** — gateway propio. Expone:
  - `GET /health`
  - `GET /skills`
  - `POST /agents/{skill}/run` (ejecuta un skill de agente)
  - `POST /rag/ingest`, `GET /rag/query`
  - Instrumentado con OpenTelemetry/OpenInference hacia Phoenix.
- **Agentes / skills (`app/agents/`)** — runtime mínimo que registra
  skills (`summarizer`, `rag_qa`), valida su entrada con Pydantic y ejecuta.
- **RAG (`app/rag/`)** — ingesta con chunking simple + embeddings de
  Ollama, índice JSON en disco, retriever por similitud coseno en memoria.
  Sin vector DB dedicada en Fase 1 (ver sección 4.3, trade-offs).
- **Prompts (`app/prompts/`)** — plantillas de texto versionadas en el
  repo, cargadas por nombre.
- **Phoenix** — recibe las trazas OTLP de cada llamada al modelo.
- **Evals (`evals/`)** — promptfoo, DeepEval y Ragas corren *fuera* del
  contenedor de la API, contra el gateway HTTP o contra Ollama
  directamente, para simular cómo un consumidor real probaría el sistema.
- **Seguridad (`evals/security/`)** — garak y el redteam de promptfoo
  corren contra Ollama directamente; ModelScan se documenta como paso
  previo a cargar artefactos de terceros.

### 4.2 Flujo (ver también `docs/diagram.md`)

1. El usuario/desarrollador ejecuta `scripts/up.sh` → se levantan Ollama,
   API y Phoenix, y se descargan los modelos configurados.
2. El usuario llama a un skill de agente (`POST /agents/rag_qa/run`) o una
   suite de pruebas (`scripts/run_prompt_tests.sh`, etc.).
3. La API valida la entrada, ejecuta el skill: el skill de RAG consulta el
   retriever local, arma el prompt con contexto, y llama a Ollama vía el
   cliente LLM propio.
4. Cada llamada al modelo queda instrumentada y se envía como traza OTLP a
   Phoenix (visible en `http://localhost:6006`).
5. Los módulos de `evals/` (promptfoo, DeepEval, Ragas) llaman al mismo
   gateway (o directo a Ollama, según el caso) y generan métricas/reportes.
6. Los módulos de seguridad (garak, promptfoo redteam) atacan el modelo
   local y generan reportes de vulnerabilidad para revisión manual.

### 4.3 Decisiones y trade-offs

- **RAG sin vector DB dedicada**: reduce un contenedor y una dependencia
  operativa. Trade-off: no escala más allá de cientos/pocos miles de
  chunks y no tiene persistencia transaccional. Aceptable para un
  laboratorio; documentado el reemplazo por Chroma/Qdrant/pgvector como
  próximo paso si el volumen de documentos crece.
- **Phoenix en vez de Langfuse**: menos infraestructura, pero licencia
  ELv2 en vez de MIT (ver `docs/security-notes.md`) y menos features de
  gestión de prompts. Aceptable para un solo usuario local.
- **Runtime de agentes propio en vez de LangGraph/CrewAI**: menos poder
  expresivo (no hay grafos de estado, no hay checkpointing, no hay
  loops/branching), pero cero dependencias pesadas y 100% explicable en
  ~80 líneas de código. Documentado el upgrade path en la sección 2.
- **Herramientas de evaluación fuera del contenedor de la API**: evita que
  la imagen de producción del laboratorio cargue con dependencias de
  testing (deepeval, ragas, requests de terceros), a costa de requerir
  Node.js/Python en el host para correr las suites. Se documenta como
  aceptable porque este es un laboratorio de desarrollo, no un despliegue
  productivo — en Fase 2 esto se resuelve con jobs de CI separados (ver
  `docs/phase-2-multicloud.md`).
- **Modelos pequeños por defecto (`llama3.2:1b`)**: prioriza que el
  laboratorio funcione en cualquier laptop sin GPU. Trade-off explícito:
  un modelo de 1B es mucho menos capaz que uno de producción, y las
  métricas de DeepEval/Ragas con un juez de 1B son una señal aproximada,
  no un ground truth (ver `docs/testing-playbook.md`).

---

## 5. Qué es MVP, qué es opcional, qué es Fase 2 (Paso 7)

**MVP (implementado y funcional en este repo):**
- Ollama + API propia + Phoenix vía Docker Compose.
- 2 skills de agente (summarizer, rag_qa) con contrato tipado.
- RAG mínimo (ingesta + retriever + endpoint).
- Ejemplo funcional de promptfoo (prompt-level + end-to-end vía API).
- Ejemplo funcional de DeepEval (contra el gateway, con juez local).
- Ejemplo funcional de Ragas (pipeline RAG completo).
- Base de red teaming (promptfoo redteam) + documentación de garak.
- Documentación de ModelScan (uso bajo demanda, no bloqueante).
- Observabilidad de trazas con Phoenix.
- Scripts de automatización para todo lo anterior.

**Opcional (documentado, código de ejemplo mínimo, no crítico para el
MVP):**
- garak como CLI instalable bajo demanda (no está en `requirements.txt` de
  la API a propósito).
- LocalAI como reemplazo de Ollama (documentado, no instalado).

**Fase 2 (solo diseñado, ver `docs/phase-2-multicloud.md`):**
- Despliegue en DigitalOcean / AWS / Azure.
- vLLM/Triton/KServe para serving a escala con GPU.
- LangGraph/CrewAI si los agentes crecen a multi-paso.
- Langfuse/Opik/MLflow si se necesita gestión de prompts o registry de
  modelos.
- llm-guard como guardrail de runtime.
- CI/CD con GitHub Actions.
