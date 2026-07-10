# ai-testing-lab

Laboratorio personal, 100% local y sin costo, para probar modelos de IA,
prompts, agentes/skills y pipelines RAG — con evaluación automatizada
(calidad, RAG, seguridad) y observabilidad de trazas. Diseñado para
escalar después a un despliegue multi-cloud portable (DigitalOcean, AWS,
Azure) sin rediseñar la arquitectura base.

> Ver `docs/architecture.md` para la clasificación completa de los
> repositorios open source analizados como referencia, el stack elegido y
> las decisiones de diseño. Ver `docs/diagram.md` para el diagrama del
> sistema.

## Inspiración visual

<img src="docs/assets/inspiration-ai-ml-ops.png" alt="Referencia visual de estilo: AI / ML Ops System Design (fondo oscuro, bloques funcionales, flechas de flujo)" width="480">

Esta imagen ("AI / ML Ops System Design") se usó **únicamente como
referencia de estilo visual** (fondo oscuro, tarjetas redondeadas
agrupando componentes, flechas de flujo con colores) para diseñar la
infografía propia del laboratorio. **No representa la arquitectura de
`ai-testing-lab`** — es un diagrama genérico de MLOps de terceros, sin
relación con este proyecto. La arquitectura real, con sus propios bloques
y flujo, está en `docs/diagram.md` ("AI Testing Lab Architecture").

## Qué incluye la Fase 1 (local, implementada en este repo)

- **Model serving**: Ollama, con interfaz compatible con OpenAI.
- **API gateway propia** (FastAPI) que expone agentes/skills y RAG.
- **Agentes/skills**: runtime propio y minimalista con 2 skills de ejemplo
  (`summarizer`, `rag_qa`).
- **RAG mínimo**: ingesta + índice + retriever, sin vector DB dedicada.
- **Testing de prompts**: promptfoo (prompt-level y end-to-end vía API).
- **Testing de la app LLM**: DeepEval, con juez 100% local.
- **Evaluación de RAG**: Ragas, con LLM/embeddings 100% locales.
- **Seguridad / red teaming**: promptfoo redteam + garak (documentado) +
  ModelScan (documentado, uso bajo demanda).
- **Observabilidad**: Arize Phoenix (trazas OTLP de cada llamada al modelo).
- **Scripts de automatización** para levantar, probar y validar todo.

## Requisitos

- Docker + Docker Compose v2.
- Node.js 18+ (opcional, solo para `promptfoo`).
- Python 3.11+ (opcional, solo para `DeepEval`/`Ragas`, cada uno con su
  propio virtualenv gestionado por los scripts).
- ~4-8 GB de RAM libres para correr un modelo pequeño local con margen.

## Quickstart

```bash
git clone <este-repo> ai-testing-lab   # o usa la carpeta ya generada
cd ai-testing-lab

./scripts/bootstrap.sh   # crea .env desde .env.example, valida dependencias
./scripts/up.sh          # levanta ollama + api + phoenix, descarga modelos
./scripts/health_check.sh

# Indexa los documentos de ejemplo para RAG
curl -X POST http://localhost:8080/rag/ingest

# Prueba un skill de agente
curl -X POST http://localhost:8080/agents/summarizer/run \
  -H "Content-Type: application/json" \
  -d '{"payload": {"text": "El laboratorio corre en local con Docker Compose.", "max_sentences": 1}}'

curl -X POST http://localhost:8080/agents/rag_qa/run \
  -H "Content-Type: application/json" \
  -d '{"payload": {"question": "¿Con qué se debe escanear un modelo de terceros?"}}'
```

Abre http://localhost:6006 para ver las trazas en Arize Phoenix.

## Correr las suites de evaluación

```bash
./scripts/run_prompt_tests.sh     # promptfoo
./scripts/run_deepeval.sh         # DeepEval
./scripts/run_ragas.sh            # Ragas
./scripts/run_security_checks.sh  # red teaming (promptfoo + garak si está instalado)
```

Ver `docs/testing-playbook.md` para cuándo usar cada una y cómo interpretar
los resultados.

## Estructura del repositorio

```
ai-testing-lab/
├── docker-compose.yml       # ollama + api + phoenix
├── .env.example
├── LICENSE                  # MIT (código original de este repo)
├── ATTRIBUTIONS.md          # licencias de todas las dependencias de terceros
├── app/                     # aplicación propia
│   ├── api/                 # gateway FastAPI (punto único de entrada)
│   ├── agents/               # runtime de agentes + skills reutilizables
│   ├── prompts/              # plantillas de prompt versionadas
│   ├── rag/                  # ingesta + retriever + documentos de ejemplo
│   ├── core/                  # config, cliente LLM, tracing
│   └── config/                # configuración declarativa de referencia
├── evals/                   # todo lo relacionado a evaluación
│   ├── promptfoo/             # testing de prompts
│   ├── deepeval/              # testing de la app LLM
│   ├── ragas/                 # evaluación de RAG
│   └── security/               # red teaming (garak, promptfoo redteam) + ModelScan
├── observability/
│   └── phoenix/                # cómo ver trazas, por qué Phoenix y no Langfuse
├── scripts/                 # automatización (levantar, probar, validar)
├── docs/                    # arquitectura, playbook, seguridad, Fase 2, diagrama
└── infra/future/             # diseño de Fase 2 (DigitalOcean, AWS, Azure) — solo diseño
```

## Documentación

- `docs/architecture.md` — clasificación de repos de referencia, stack
  elegido, arquitectura, decisiones y trade-offs, qué es MVP vs Fase 2.
- `docs/testing-playbook.md` — cómo y cuándo usar cada capa de testing.
- `docs/security-notes.md` — riesgos de terceros, datos sensibles,
  licencias, qué es original vs. de terceros.
- `docs/phase-2-multicloud.md` — diseño del roadmap multi-cloud (2A/2B/2C).
- `docs/diagram.md` — diagrama Mermaid del sistema + explicación + layout
  visual sugerido para convertirlo en infografía.

## Qué es MVP, qué es opcional, qué es Fase 2

Ver la sección 5 de `docs/architecture.md` para el detalle completo. En
resumen: todo lo listado arriba en "Qué incluye la Fase 1" es MVP
funcional; LocalAI y garak como CLI quedan documentados como opcionales;
el despliegue a nube, Kubernetes, LangGraph/CrewAI, Langfuse/Opik/MLflow y
llm-guard quedan diseñados para la Fase 2.

## Notas importantes

- Este repo no depende de ningún servicio de nube pago en la Fase 1.
- No incluyas datos sensibles reales en `app/rag/sample_docs/` ni en
  ningún dataset de prueba — ver `docs/security-notes.md`.
- Antes de correr herramientas de red teaming (garak, promptfoo redteam),
  lee las advertencias en `evals/security/garak/README.md` y
  `scripts/run_security_checks.sh`.
