# Notas de seguridad — ai-testing-lab

## 1. Riesgos de ejecutar herramientas/scripts de terceros

Este laboratorio instala y ejecuta CLIs y librerías de terceros (Ollama,
promptfoo, DeepEval, Ragas, garak, ModelScan). Antes de instalar cualquiera:

- **Usa siempre las imágenes/paquetes oficiales** referenciados en este
  repo (`ollama/ollama`, `arizephoenix/phoenix` en Docker Hub;
  `promptfoo`, `deepeval`, `ragas`, `garak`, `modelscan` en npm/PyPI bajo
  sus nombres oficiales). No sustituyas por forks no verificados.
- **Pinea versiones** en `requirements.txt` (ya hecho en este repo) para
  evitar que una actualización silenciosa introduzca un cambio de
  comportamiento o una dependencia comprometida sin que te des cuenta.
- **Aísla entornos**: las herramientas de evaluación/seguridad corren en
  virtualenvs propios (`evals/*/.venv`, ver `scripts/run_deepeval.sh` y
  `run_ragas.sh`) o en contenedores separados, nunca mezcladas con las
  dependencias de producción de `app/`.
- **garak genera contenido adversarial real** (intentos de jailbreak,
  contenido dañino simulado). Ejecútalo solo contra tu modelo local, no
  compartas los prompts generados fuera de este contexto de red teaming
  defensivo, y no los reutilices para otros fines.
- **No expongas los puertos del stack a internet** (`11434`, `8080`,
  `6006`, `4317`). `docker-compose.yml` los publica explícitamente en
  `127.0.0.1:<puerto>` (no `0.0.0.0`), así que por defecto solo son
  alcanzables desde la misma máquina, ni siquiera desde otros equipos de
  la misma red local. Si necesitas acceso remoto temporal, usa un túnel
  SSH; no cambies el bind a `0.0.0.0`/quites el prefijo `127.0.0.1:` sin
  agregar autenticación real delante.

## 2. Datos sensibles

- **No coloques datos personales, credenciales, contratos, información de
  clientes ni cualquier dato confidencial real** en `app/rag/sample_docs/`
  ni en ningún dataset de prueba de este laboratorio. Los documentos de
  ejemplo incluidos son ficticios a propósito.
- Si vas a usar este laboratorio para probar casos con datos reales de un
  proyecto de trabajo, **anonimiza o enmascara** esos datos antes de
  indexarlos (nombres, cédulas, correos, teléfonos, cuentas). El índice
  RAG se persiste en disco (`rag_index` volume) sin cifrado — trátalo como
  no apto para datos sensibles en la Fase 1.
- `.env` nunca debe subirse a git (ya está pensado para eso — usa
  `.env.example` como plantilla pública).

## 3. Licencias — qué implica cada una para tu uso

Ver también `ATTRIBUTIONS.md` para la lista completa con enlaces.

| Categoría de licencia | Herramientas | Qué significa para ti (uso interno/laboratorio) |
|---|---|---|
| MIT | Ollama, promptfoo, LocalAI, langfuse (core), garak, modelscan, llm-guard, langgraph, crewAI, pydantic-ai, agentevals, openevals, lm-evaluation-harness, openai/evals, openai/simple-evals | Permisiva. Puedes usar, modificar y redistribuir libremente, manteniendo el aviso de copyright/licencia si redistribuyes el código. |
| Apache-2.0 | DeepEval, Ragas, Giskard-oss, Giskard-skills, vLLM, BentoML, Ray, KServe, opik, MLflow | Permisiva, similar a MIT, con una cláusula explícita de concesión de patentes. Sin restricciones relevantes para uso interno. |
| Elastic License 2.0 (ELv2) | Arize Phoenix | Puedes usarlo, modificarlo y auto-hospedarlo libremente. **Restricción real**: no puedes ofrecerlo como servicio gestionado de terceros (SaaS) compitiendo con Elastic/Arize. Para este laboratorio (uso interno) esto no aplica. |
| BSD-3-Clause | Triton Inference Server | Permisiva, sin restricciones relevantes (no se usa en la Fase 1). |

**Nota importante**: las licencias de código abierto pueden cambiar entre
versiones (algunos proyectos han migrado de MIT/Apache a licencias más
restrictivas, o viceversa — Langfuse, por ejemplo, movió más funcionalidad
a MIT en 2025). Antes de un uso comercial o de redistribuir este
laboratorio, **verifica el archivo `LICENSE` de la versión exacta que
instales** de cada dependencia, no confíes solo en esta tabla.

## 4. Qué es original vs. qué es de terceros en este repo

- **Original (código propio de este repo)**: `app/` completo (API, agentes/
  skills, RAG, cliente LLM, config, prompts), los scripts de `scripts/`,
  toda la configuración YAML de `evals/` (son *configuraciones* que usan
  el formato público de cada herramienta, no código copiado de esos
  repos), y toda la documentación de `docs/`.
- **De terceros (instalado, no modificado)**: Ollama, Phoenix, promptfoo,
  DeepEval, Ragas, garak, ModelScan — se usan como dependencias/CLIs, sin
  copiar su código fuente a este repo.
- **Patrón/inspiración, no código**: el diseño de `app/agents/skills/`
  (contrato `Skill` con Pydantic) se inspira conceptualmente en
  Giskard-skills y pydantic-ai, pero es una implementación propia y
  deliberadamente más pequeña.

## 5. Incidencias conocidas (encontradas durante la validación de Fase 1)

Documentadas aquí para que no se repitan en Fase 2 ni se confundan con
bugs nuevos si vuelven a aparecer.

- **`openai==1.51.0` incompatible con `httpx>=0.28`**: esa versión de
  `openai` todavía pasa un argumento `proxies=` a `httpx.Client`, que
  `httpx` eliminó en la 0.28. Si `httpx` no queda fijado explícitamente,
  `pip` puede resolver la última versión y romper `app/core/llm_client.py`
  (y, por la misma razón, `evals/deepeval/local_model.py` y
  `evals/ragas/evaluate_rag.py`, que también instancian un cliente
  `OpenAI`). **Fix aplicado**: `httpx==0.27.2` fijado explícitamente en
  `app/requirements.txt`, `evals/deepeval/requirements.txt` y
  `evals/ragas/requirements.txt`.
- **Fijar `openai==1.51.0` a la vez en los 3 requirements.txt genera un
  conflicto en `evals/ragas`**: `langchain-openai==0.2.6` exige
  `openai>=1.54.0,<2.0.0`, incompatible con el pin `1.51.0`. La causa raíz
  del bug original (ver punto anterior) es `httpx`, no la versión exacta
  de `openai`. **Fix aplicado**: `evals/ragas/requirements.txt` ya no fija
  una versión exacta de `openai` — deja que `pip` resuelva una versión que
  satisfaga a `ragas` y `langchain-openai` a la vez, y mantiene
  `httpx==0.27.2` fijado (eso es lo que realmente evita el bug, sin
  importar qué versión de `openai` se resuelva).
- **Ragas con Ollama: timeouts masivos y resultados `NaN`**: por defecto
  Ragas dispara hasta 16 jobs de evaluación en paralelo (`RunConfig`
  default `max_workers=16`, `timeout=180s`), pensado para APIs remotas con
  alta concurrencia. Ollama en CPU sirve con un solo slot de inferencia
  (`OLLAMA_NUM_PARALLEL=1`), así que la mayoría de esos jobs queda en cola
  y termina en `TimeoutError` antes de que Ollama llegue a procesarlos
  (visto en la práctica: 11 de 12 jobs en timeout, CSV casi todo `NaN`).
  **Fix aplicado**: `evals/ragas/evaluate_rag.py` pasa un `RunConfig`
  propio (`max_workers=1`, `timeout=600`) que serializa las llamadas para
  que coincidan con la capacidad real de Ollama.
- **`langchain_openai.OpenAIEmbeddings` incompatible con el endpoint de
  embeddings de Ollama**: por defecto pre-tokeniza el texto con `tiktoken`
  y envía arrays de enteros (token ids) como `input` — algo que la API
  real de OpenAI acepta pero Ollama rechaza con `400 invalid input type`.
  **Fix aplicado**: `check_embedding_ctx_length=False` en la instancia de
  `OpenAIEmbeddings` de `evals/ragas/evaluate_rag.py`, para que envíe
  texto plano en vez de tokens.
- **Un modelo pequeño local puede entrar en un bucle de repetición y
  generar miles de tokens sin parar**: visto en la práctica con
  `llama3.2:1b` en un prompt interno de Ragas (>5000 tokens generados para
  lo que debía ser un veredicto corto), lo que además bloquea toda la cola
  de evaluación al correr en modo serializado. **Fix aplicado**:
  `max_tokens=512` en el `ChatOpenAI` usado como juez en
  `evals/ragas/evaluate_rag.py`.
- **`promptfoo redteam generate` exige verificación por email**: a
  diferencia de `promptfoo eval` (testing normal de prompts, sin
  registro), el comando `redteam generate` pide verificar un correo la
  primera vez que se usa. Es un requisito del propio CLI de promptfoo, no
  de este proyecto, y rompe la expectativa de "100% local, sin cuenta" que
  tiene el resto del laboratorio. **Recomendación**: si no quieres dar
  ningún dato de contacto, usa **garak** para red teaming — cubre el mismo
  objetivo (jailbreak, fuga de datos, contenido dañino) sin pedir ningún
  registro. `scripts/run_security_checks.sh` corre garak primero y trata
  el paso de promptfoo como opcional/best-effort por esta misma razón.
- **`python3` en Windows puede resolver a un stub roto**: en instalaciones
  de Windows con los "alias de ejecución de aplicaciones" activados,
  `python3` (y a veces `python`) en el PATH apuntan a un stub de
  Microsoft Store que no ejecuta nada real (sale con error al invocarlo).
  `command -v` no detecta esto porque el binario "existe". **Fix
  aplicado**: `scripts/lib/find_python.sh` valida cada candidato
  ejecutando `--version` de verdad, probando `python3`, `python` y
  `py -3` en ese orden, no solo su presencia en el PATH.
- **`pip install --upgrade pip` falla en Windows dentro de un venv recién
  creado**: pip no puede reemplazar su propio ejecutable mientras está
  corriendo en Windows, y sugiere usar `python -m pip install --upgrade
  pip` en su lugar. **Fix aplicado**: `scripts/run_deepeval.sh` y
  `scripts/run_ragas.sh` usan `python -m pip ...` en vez de `pip ...`
  directo (forma además más portable entre plataformas).

## 6. Recomendaciones adicionales

- Ejecuta `docker compose down --volumes` (`scripts/down.sh --volumes`)
  antes de desechar el laboratorio si indexaste algo sensible por error.
- Revisa periódicamente `docker images` y actualiza las imágenes base
  (`ollama/ollama`, `arizephoenix/phoenix`, `python:3.11-slim`) para recibir
  parches de seguridad del sistema operativo base.
- Si en algún momento conectas este laboratorio a un modelo o API de un
  proveedor real (no local), nunca commitees la API key — usa `.env` y
  revisa `git status`/`git diff` antes de cada commit.
