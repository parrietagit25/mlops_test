#!/usr/bin/env bash
# Corre las pruebas de prompts con promptfoo (evals/promptfoo).
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] && set -a && source .env && set +a

command -v npx >/dev/null 2>&1 || {
  echo "ERROR: se necesita Node.js/npx para correr promptfoo." >&2
  echo "Instala Node.js 18+ y vuelve a intentar." >&2
  exit 1
}

echo "==> Pruebas de prompt (summarizer, modelo directo)"
(cd evals/promptfoo && npx --yes promptfoo@latest eval -c promptfooconfig.yaml)

echo ""
echo "==> Pruebas end-to-end (rag_qa vía API)"
echo "    (requiere: docker compose up -d && curl -X POST http://localhost:${API_PORT:-8080}/rag/ingest)"
(cd evals/promptfoo && npx --yes promptfoo@latest eval -c promptfooconfig.rag.yaml)

echo ""
echo "==> Para ver los resultados en un visor web: npx promptfoo@latest view"
