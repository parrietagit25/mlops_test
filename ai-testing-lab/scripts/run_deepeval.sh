#!/usr/bin/env bash
# Corre las pruebas de DeepEval contra el gateway (requiere el stack arriba).
# En Docker (EVAL-RUNTIME-1): usa AILAB_DEEPEVAL_PYTHON (venv horneado en /opt).
# En host: crea/usa evals/deepeval/.venv local si hace falta.
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck source=lib/source_lab_env.sh
source "$(dirname "$0")/lib/source_lab_env.sh"
source_lab_env

if [ -n "${AILAB_DEEPEVAL_PYTHON:-}" ] && [ -x "${AILAB_DEEPEVAL_PYTHON}" ]; then
  PY="${AILAB_DEEPEVAL_PYTHON}"
  echo "==> Usando intérprete horneado DeepEval: ${PY}"
else
  # shellcheck source=lib/find_python.sh
  source "$(dirname "$0")/lib/find_python.sh"
  find_python || exit 1

  VENV_DIR="evals/deepeval/.venv"
  # Evitar .venv de Windows (Scripts/) en Linux.
  if [ -d "$VENV_DIR/Scripts" ] && [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "AVISO: se detectó un .venv incompatible (Windows Scripts/). Se recrea." >&2
    rm -rf "$VENV_DIR"
  fi
  if [ ! -x "$VENV_DIR/bin/python" ] && [ ! -x "$VENV_DIR/Scripts/python.exe" ]; then
    echo "==> Creando entorno virtual para DeepEval..."
    "${PY_CMD[@]}" -m venv "$VENV_DIR"
  fi
  # shellcheck disable=SC1091
  if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
  elif [ -f "$VENV_DIR/Scripts/activate" ]; then
    source "$VENV_DIR/Scripts/activate"
  else
    echo "ERROR: no se pudo activar el venv de DeepEval." >&2
    exit 1
  fi
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet -r evals/deepeval/requirements.txt
  PY="python"
fi

echo "==> Ejecutando pytest sobre evals/deepeval"
(cd evals/deepeval && "$PY" -m pytest -v)
