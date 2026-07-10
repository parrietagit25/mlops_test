# Red teaming con garak (NVIDIA/garak, Apache-2.0)

`garak` es un scanner de vulnerabilidades de LLM (jailbreaks, prompt
injection, fuga de datos, toxicidad, etc.). No se reimplementa aquí: se usa
tal cual como herramienta CLI de terceros, apuntada contra el modelo local.

## Advertencia de seguridad antes de usarlo

- Ejecuta `garak` **solo contra el modelo local (Ollama)**, nunca contra un
  endpoint de producción o de un tercero sin autorización explícita.
- `garak` genera prompts adversariales reales (jailbreaks, contenido dañino
  simulado). Es un uso legítimo de red teaming defensivo en tu propio
  laboratorio, pero no reutilices esos prompts fuera de este contexto.
- Instálalo en un entorno virtual dedicado (`evals/security/garak/venv`) o en
  el contenedor `api` bajo demanda; no lo mezcles con las dependencias de
  producción de `app/`.
- Revisa los reportes localmente (`.jsonl` / HTML) antes de compartirlos:
  pueden contener el contenido adversarial generado.

## Instalación (entorno local, no en Docker por defecto)

```bash
python -m venv evals/security/garak/.venv
source evals/security/garak/.venv/bin/activate   # En Windows: .venv\Scripts\activate
pip install garak
```

## Ejecución mínima contra el modelo local

garak trae un generador nativo para endpoints compatibles con OpenAI:

```bash
export OPENAI_API_KEY=ollama-local-no-key-needed
export OPENAI_BASE_URL=http://localhost:11434/v1

garak \
  --model_type openai \
  --model_name llama3.2:1b \
  --probes promptinject,dan,leakreplay \
  --generations 2 \
  --report_prefix evals/security/garak/reports/smoke
```

Esto corre un subconjunto pequeño de "probes" (ataques conocidos) para un
smoke test rápido. La lista completa de probes es mucho más grande; úsala
con criterio: más probes = más tiempo de ejecución, no más costo (todo es
local), pero sí más tiempo de laptop/CPU.

Ver `scripts/run_security_checks.sh` para un wrapper que ejecuta este smoke
test automáticamente si `garak` está instalado.

## Qué mirar en el reporte

- `pass rate` por probe: qué tan seguido el modelo resistió el ataque.
- Los prompts y respuestas específicas donde falló, para decidir si el
  system prompt o el skill necesitan un guardrail adicional.
