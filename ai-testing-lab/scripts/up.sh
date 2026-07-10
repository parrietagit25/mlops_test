#!/usr/bin/env bash
# Levanta todo el stack local y descarga los modelos si hace falta.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || ./scripts/bootstrap.sh

echo "==> Levantando docker compose (ollama, api, phoenix)..."
docker compose up -d

echo "==> Esperando a que Ollama esté saludable..."
for i in $(seq 1 30); do
  status="$(docker inspect -f '{{.State.Health.Status}}' ailab-ollama 2>/dev/null || echo starting)"
  [ "$status" = "healthy" ] && break
  sleep 2
done

./scripts/pull_models.sh

echo ""
echo "==> Stack arriba:"
echo "  - API:      http://localhost:${API_PORT:-8080}/health"
echo "  - Ollama:   http://localhost:${OLLAMA_PORT:-11434}"
echo "  - Phoenix:  http://localhost:${PHOENIX_UI_PORT:-6006}"
echo ""
echo "Siguiente paso sugerido: curl -X POST http://localhost:${API_PORT:-8080}/rag/ingest"
