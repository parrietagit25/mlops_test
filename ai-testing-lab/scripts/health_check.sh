#!/usr/bin/env bash
# Validación rápida de que el stack está sano.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] && set -a && source .env && set +a

api_port="${API_PORT:-8080}"
ollama_port="${OLLAMA_PORT:-11434}"
phoenix_port="${PHOENIX_UI_PORT:-6006}"

check() {
  name="$1"; url="$2"
  if curl -fsS --max-time 5 "$url" >/dev/null 2>&1; then
    echo "  [OK]   $name ($url)"
  else
    echo "  [FAIL] $name ($url)"
    return 1
  fi
}

echo "==> Chequeando servicios..."
failed=0
check "API"     "http://localhost:${api_port}/health" || failed=1
check "Ollama"  "http://localhost:${ollama_port}/api/tags" || failed=1
check "Phoenix" "http://localhost:${phoenix_port}" || failed=1

if [ "$failed" -eq 1 ]; then
  echo "==> Uno o más servicios no responden. Revisa 'docker compose logs -f'."
  exit 1
fi

echo "==> Todo saludable."
