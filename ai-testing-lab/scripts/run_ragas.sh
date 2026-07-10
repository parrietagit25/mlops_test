#!/usr/bin/env bash
# Corre la evaluación de RAG con Ragas (requiere el stack arriba e índice creado).
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] && set -a && source .env && set +a

# shellcheck source=lib/find_python.sh
source "$(dirname "$0")/lib/find_python.sh"
find_python || exit 1

VENV_DIR="evals/ragas/.venv"
if [ ! -d "$VENV_DIR" ]; then
  echo "==> Creando entorno virtual para Ragas..."
  "${PY_CMD[@]}" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate" 2>/dev/null || source "$VENV_DIR/Scripts/activate"

# `python -m pip` (no `pip` directo): en Windows, `pip install --upgrade pip`
# falla porque pip no puede reemplazar su propio .exe mientras corre.
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r evals/ragas/requirements.txt

echo "==> Asegurando índice RAG (POST /rag/ingest)..."
curl -fsS -X POST "http://localhost:${API_PORT:-8080}/rag/ingest" || {
  echo "ERROR: no se pudo indexar. ¿Está el stack arriba? (scripts/up.sh)" >&2
  exit 1
}

echo ""
echo "==> Ejecutando evaluación Ragas"
python evals/ragas/evaluate_rag.py
