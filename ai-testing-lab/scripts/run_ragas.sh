#!/usr/bin/env bash
# Corre la evaluación de RAG con Ragas (requiere el stack arriba e índice creado).
# En Docker (EVAL-RUNTIME-1): usa AILAB_RAGAS_PYTHON (venv horneado en /opt).
# En host: crea/usa evals/ragas/.venv local si hace falta.
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck source=lib/source_lab_env.sh
source "$(dirname "$0")/lib/source_lab_env.sh"
source_lab_env

if [ -n "${AILAB_RAGAS_PYTHON:-}" ] && [ -x "${AILAB_RAGAS_PYTHON}" ]; then
  PY="${AILAB_RAGAS_PYTHON}"
  echo "==> Usando intérprete horneado Ragas: ${PY}"
else
  # shellcheck source=lib/find_python.sh
  source "$(dirname "$0")/lib/find_python.sh"
  find_python || exit 1

  VENV_DIR="evals/ragas/.venv"
  if [ -d "$VENV_DIR/Scripts" ] && [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "AVISO: se detectó un .venv incompatible (Windows Scripts/). Se recrea." >&2
    rm -rf "$VENV_DIR"
  fi
  if [ ! -x "$VENV_DIR/bin/python" ] && [ ! -x "$VENV_DIR/Scripts/python.exe" ]; then
    echo "==> Creando entorno virtual para Ragas..."
    "${PY_CMD[@]}" -m venv "$VENV_DIR"
  fi
  # shellcheck disable=SC1091
  if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
  elif [ -f "$VENV_DIR/Scripts/activate" ]; then
    source "$VENV_DIR/Scripts/activate"
  else
    echo "ERROR: no se pudo activar el venv de Ragas." >&2
    exit 1
  fi
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet -r evals/ragas/requirements.txt
  PY="python"
fi

INGEST_URL="${API_BASE_URL:-http://localhost:${API_PORT:-8080}}/rag/ingest"
echo "==> Asegurando índice RAG (POST ${INGEST_URL})..."
curl -fsS -X POST "${INGEST_URL}" || {
  echo "ERROR: no se pudo indexar. ¿Está el stack arriba? (scripts/up.sh)" >&2
  exit 1
}

echo ""
echo "==> Ejecutando evaluación Ragas"
"$PY" evals/ragas/evaluate_rag.py
