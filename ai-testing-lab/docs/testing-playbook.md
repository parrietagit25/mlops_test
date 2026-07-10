# Testing Playbook — ai-testing-lab

Guía práctica de cómo y cuándo usar cada capa de testing del laboratorio.

## 0. Antes de empezar

```bash
./scripts/bootstrap.sh   # crea .env
./scripts/up.sh           # levanta ollama + api + phoenix, descarga modelos
curl -X POST http://localhost:8080/rag/ingest   # indexa los docs de ejemplo
./scripts/health_check.sh
```

## 1. Testing de prompts (promptfoo)

**Cuándo usarlo:** cada vez que cambies una plantilla de prompt
(`app/prompts/templates/*.txt` o `evals/promptfoo/prompts/*.txt`) o quieras
comparar el mismo prompt contra dos modelos/temperaturas distintas.

```bash
./scripts/run_prompt_tests.sh
npx promptfoo@latest view   # visor web con el detalle de cada caso
```

Qué valida el ejemplo incluido (`evals/promptfoo/promptfooconfig.yaml`):
- Que el resumen no exceda el número de oraciones pedido.
- Que no invente días de la semana que no están en el texto (alucinación
  básica).
- Que responda en el idioma correcto (vía `llm-rubric`, un juez LLM).

Y el ejemplo end-to-end (`promptfooconfig.rag.yaml`) valida el pipeline
completo (retriever + prompt + modelo) a través de la API, no solo el
prompt aislado.

**Cómo agregar un caso nuevo:** añade un `tests:` con `vars` y `assert`. Usa
`type: javascript` para reglas deterministas (longitud, formato, palabras
prohibidas) y `type: llm-rubric` solo cuando la validación es realmente
subjetiva (tono, idioma, coherencia) — los rubrics con un modelo de 1B como
juez son menos confiables, úsalos con criterio.

## 2. Testing de la aplicación LLM (DeepEval)

**Cuándo usarlo:** para validar el comportamiento de un *skill completo*
(no solo el prompt), con métricas de calidad tipo pytest que fallan el
build si bajan de un umbral.

```bash
./scripts/run_deepeval.sh
```

El juez usado es local (`evals/deepeval/local_model.py`, apunta a Ollama),
así que las pruebas corren sin costo. **Trade-off honesto**: un modelo
pequeño como juez comete más errores de calibración que GPT-4. Usa
umbrales (`threshold=`) conservadores y trata las métricas como una señal
de regresión relativa (¿bajó respecto a la corrida anterior?), no como un
score absoluto comparable con benchmarks publicados.

**Cómo agregar un test nuevo:** copia el patrón de `test_basic.py` — llama
al endpoint del skill, arma un `LLMTestCase`, elige la métrica relevante
(`AnswerRelevancyMetric`, `FaithfulnessMetric`, o una determinista con
`assert` plano de Python si no necesitas juicio de LLM).

## 3. Evaluación de RAG (Ragas)

**Cuándo usarlo:** cada vez que cambies el chunking, el modelo de
embeddings, el prompt de RAG, o agregues/quites documentos fuente.

```bash
./scripts/run_ragas.sh
```

Métricas incluidas: `faithfulness` (¿la respuesta se sostiene en el
contexto recuperado?), `answer_relevancy` (¿responde la pregunta?),
`context_precision`/`context_recall` (¿el retriever trajo los chunks
correctos?). Resultados en `evals/ragas/last_run_results.csv`.

**Señal de alarma a vigilar:** si `context_precision`/`recall` es bajo pero
`faithfulness` es alto, el problema está en el *retriever* (chunking,
embeddings), no en el modelo generador — no gastes tiempo ajustando el
prompt en ese caso.

## 4. Seguridad / Red teaming

**Cuándo usarlo:** antes de exponer un nuevo skill o cambiar el system
prompt de forma significativa; periódicamente si el laboratorio pasa a
tener más de un usuario.

```bash
./scripts/run_security_checks.sh
```

Ver `docs/security-notes.md` para el detalle de riesgos y buenas prácticas
al ejecutar estas herramientas.

## 5. Orden recomendado en un ciclo de cambio

1. Cambias un prompt/skill.
2. `run_prompt_tests.sh` — feedback más rápido, granularidad de prompt.
3. `run_deepeval.sh` — feedback a nivel de skill completo.
4. Si tocaste RAG: `run_ragas.sh`.
5. Si tocaste el system prompt o agregaste un skill expuesto: `run_security_checks.sh`.
6. Revisa las trazas en Phoenix (http://localhost:6006) si algo no cuadra.

## 6. Qué NO está cubierto todavía (a propósito)

- Pruebas de carga/concurrencia (no aplica a un laboratorio de un usuario).
- Evaluación de trayectorias de agentes multi-paso (no hay agentes
  multi-paso en el MVP; ver `langchain-ai/agentevals` en
  `docs/architecture.md` como candidato de Fase 2).
- CI automatizado corriendo estas suites en cada commit (ver
  `docs/phase-2-multicloud.md`, sección CI/CD).
