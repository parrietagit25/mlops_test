# Observabilidad: Arize Phoenix

## Por qué Phoenix y no Langfuse en la Fase 1

El enunciado original permitía Langfuse **o** Phoenix. Se eligió Phoenix
para el MVP local por una razón concreta de simplicidad:

- **Phoenix**: un solo contenedor (`arizephoenix/phoenix`), sin base de
  datos externa obligatoria, nativo de OpenTelemetry/OpenInference. Levanta
  y ya.
- **Langfuse (v3)**: arquitectura de producción con Postgres + ClickHouse +
  Redis + almacenamiento de objetos (MinIO/S3). Es la opción correcta
  cuando el laboratorio escale a un uso más serio o multi-usuario, pero es
  sobre-ingeniería para un laboratorio de una sola persona en local.

Licencia: Phoenix se distribuye bajo **Elastic License 2.0 (ELv2)**, no
Apache/MIT. Para uso interno de laboratorio esto no es una restricción real
(la restricción de ELv2 es no ofrecerlo como servicio gestionado a
terceros), pero queda documentado en `docs/security-notes.md`.

Si más adelante prefieres Langfuse (ej. por su UI de gestión de prompts o
por preferencia de licencia MIT), el patrón de integración es el mismo:
Phoenix y Langfuse hablan OTLP, así que `app/core/tracing.py` solo
necesitaría apuntar el exporter a otro endpoint.

## Cómo levantarlo

Ya viene definido como servicio `phoenix` en el `docker-compose.yml` raíz:

```bash
docker compose up -d phoenix
```

## Cómo ver trazas, prompts y resultados

1. Abre http://localhost:6006 en el navegador.
2. Cada llamada al modelo hecha por `app/core/llm_client.py` (a través de
   `app/core/tracing.py`, que auto-instrumenta el SDK de OpenAI) aparece
   como un span en el proyecto `ai-testing-lab`.
3. Cada span incluye: prompt enviado, respuesta del modelo, modelo usado,
   latencia y (si el proveedor lo reporta) conteo de tokens.
4. Puedes filtrar por skill (`summarizer`, `rag_qa`) porque el nombre de la
   skill se añade a los metadatos del resultado y a los logs de la API.

## Qué queda fuera en la Fase 1 (a propósito)

- Dashboards personalizados / alertas: no hay necesidad real con un solo
  usuario y ejecución local.
- Evaluaciones online automáticas dentro de Phoenix (Phoenix también trae
  su propio motor de evals): se prioriza DeepEval/Ragas para evaluación,
  Phoenix se usa solo como *trace store*, para no duplicar herramientas.
