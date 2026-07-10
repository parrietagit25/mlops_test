#!/usr/bin/env bash
# Corre las pruebas de DeepEval contra el gateway (requiere el stack arriba).
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] && set -a && source .env && set +a

# shellcheck source=lib/find_python.sh
source "$(dirname "$0")/lib/find_python.sh"
find_python || exit 1

VENV_DIR="evals/deepeval/.venv"
if [ ! -d "$VENV_DIR" ]; then
  echo "==> Creando entorno virtual para DeepEval..."
  "${PY_CMD[@]}" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate" 2>/dev/null || source "$VENV_DIR/Scripts/activate"

pip install --quiet --upgrade pip
pip install --quiet -r evals/deepeval/requirements.txt

echo "==> Ejecutando pytest sobre evals/deepeval"
(cd evals/deepeval && pytest -v)
