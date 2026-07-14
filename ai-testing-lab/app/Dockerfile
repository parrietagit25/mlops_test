# Build context: raíz del laboratorio (docker-compose build.context: .).
# El código del Gateway vive en app/; los requirements de evals se hornean
# en /opt/ailab/venvs (EVAL-RUNTIME-1). Node/Promptfoo/garak NO se instalan.

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AILAB_DEEPEVAL_PYTHON=/opt/ailab/venvs/deepeval/bin/python \
    AILAB_RAGAS_PYTHON=/opt/ailab/venvs/ragas/bin/python

# bash: scripts/run_*.sh vía eval runner.
# curl: health/diagnóstico y curl a /rag/ingest desde run_ragas.
# python3-venv: ensurepip disponible por si se crean venvs de emergencia.
# Node NO se instala: promptfoo falla con mensaje claro (EVAL-RUNTIME-2).
RUN apt-get update \
    && apt-get install -y --no-install-recommends bash curl python3-venv \
    && rm -rf /var/lib/apt/lists/*

COPY app/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Venvs de evaluación preparados en build (no bajo el volumen /lab/evals).
COPY evals/deepeval/requirements.txt /tmp/deepeval-requirements.txt
COPY evals/ragas/requirements.txt /tmp/ragas-requirements.txt
RUN python -m venv /opt/ailab/venvs/deepeval \
    && /opt/ailab/venvs/deepeval/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/ailab/venvs/deepeval/bin/pip install --no-cache-dir -r /tmp/deepeval-requirements.txt \
    && python -m venv /opt/ailab/venvs/ragas \
    && /opt/ailab/venvs/ragas/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/ailab/venvs/ragas/bin/pip install --no-cache-dir -r /tmp/ragas-requirements.txt \
    && rm -f /tmp/deepeval-requirements.txt /tmp/ragas-requirements.txt

COPY app/ /app/

EXPOSE 8080

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]
