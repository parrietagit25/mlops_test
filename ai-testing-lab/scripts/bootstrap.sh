#!/usr/bin/env bash
# Prepara el entorno local por primera vez: crea .env, valida dependencias.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> ai-testing-lab · bootstrap"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "  - .env creado a partir de .env.example"
else
  echo "  - .env ya existe, no se sobrescribe"
fi

command -v docker >/dev/null 2>&1 || {
  echo "ERROR: docker no está instalado o no está en PATH." >&2
  exit 1
}

if docker compose version >/dev/null 2>&1; then
  echo "  - docker compose disponible"
else
  echo "ERROR: 'docker compose' (plugin v2) no está disponible." >&2
  exit 1
fi

echo "  - Node/npm (opcional, requerido solo para promptfoo):"
if command -v npx >/dev/null 2>&1; then
  echo "    npx disponible"
else
  echo "    npx NO disponible. Instala Node.js si quieres correr promptfoo."
fi

echo "  - Python (opcional, requerido para deepeval/ragas):"
if command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then
  echo "    python disponible"
else
  echo "    python NO disponible. Instala Python 3.11+ para deepeval/ragas."
fi

echo "==> Listo. Siguiente paso: scripts/up.sh"
