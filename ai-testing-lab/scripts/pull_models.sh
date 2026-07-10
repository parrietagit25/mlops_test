#!/usr/bin/env bash
# Descarga los modelos configurados en .env dentro del contenedor de Ollama.
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
[ -f .env ] && set -a && source .env && set +a

CHAT_MODEL="${OLLAMA_CHAT_MODEL:-llama3.2:1b}"
EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"

echo "==> Descargando modelo de chat: ${CHAT_MODEL}"
docker compose exec -T ollama ollama pull "${CHAT_MODEL}"

echo "==> Descargando modelo de embeddings: ${EMBED_MODEL}"
docker compose exec -T ollama ollama pull "${EMBED_MODEL}"

echo "==> Modelos disponibles:"
docker compose exec -T ollama ollama list
