#!/usr/bin/env bash
# Carga .env sin pisar URLs ya inyectadas por Compose / eval_runner.
# Uso: source "$(dirname "$0")/lib/source_lab_env.sh"  (desde scripts/*.sh)

source_lab_env() {
  local preserve_ollama="${OLLAMA_BASE_URL:-}"
  local preserve_openai="${OPENAI_BASE_URL:-}"
  local preserve_api="${API_BASE_URL:-}"
  local preserve_key="${OPENAI_API_KEY:-}"
  local preserve_chat="${OLLAMA_CHAT_MODEL:-}"
  local preserve_embed="${OLLAMA_EMBED_MODEL:-}"

  if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
  fi

  [ -n "$preserve_ollama" ] && export OLLAMA_BASE_URL="$preserve_ollama"
  [ -n "$preserve_openai" ] && export OPENAI_BASE_URL="$preserve_openai"
  [ -n "$preserve_api" ] && export API_BASE_URL="$preserve_api"
  [ -n "$preserve_key" ] && export OPENAI_API_KEY="$preserve_key"
  [ -n "$preserve_chat" ] && export OLLAMA_CHAT_MODEL="$preserve_chat"
  [ -n "$preserve_embed" ] && export OLLAMA_EMBED_MODEL="$preserve_embed"
}
