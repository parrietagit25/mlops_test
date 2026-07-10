#!/usr/bin/env bash
# Apaga el stack local. Usa --volumes para borrar también los datos
# persistidos (modelos descargados, índice RAG, trazas de Phoenix).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ "${1:-}" = "--volumes" ]; then
  echo "==> Apagando y borrando volúmenes (modelos, índice RAG, trazas)..."
  docker compose down --volumes
else
  echo "==> Apagando stack (los volúmenes se conservan)..."
  docker compose down
fi
