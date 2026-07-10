#!/usr/bin/env bash
# Detecta un intérprete de Python que realmente funcione, en Windows, Linux
# y macOS.
#
# Por qué no basta con `command -v python3`: en Windows, `python3` (y a
# veces `python`) en el PATH puede resolver al stub de "Microsoft Store App
# Execution Alias" (AppData\Local\Microsoft\WindowsApps\python3.exe), que
# "existe" para `command -v` pero al ejecutarlo solo imprime un mensaje
# pidiendo instalar Python desde la Store y termina con código de error
# (confirmado: exit code 49). El intérprete real puede estar disponible bajo
# otro nombre (`python`, o el lanzador `py -3`).
#
# Por eso cada candidato se valida ejecutando `--version` de verdad, no solo
# comprobando que el binario exista en el PATH.
#
# Uso:
#   source "$(dirname "$0")/lib/find_python.sh"
#   find_python || exit 1
#   "${PY_CMD[@]}" -m venv .venv

find_python() {
  local candidates=("python3" "python" "py -3")
  local cand parts

  for cand in "${candidates[@]}"; do
    # shellcheck disable=SC2206
    parts=($cand)
    if command -v "${parts[0]}" >/dev/null 2>&1 && "${parts[@]}" --version >/dev/null 2>&1; then
      PY_CMD=("${parts[@]}")
      echo "  - intérprete de Python detectado: ${PY_CMD[*]} ($("${PY_CMD[@]}" --version 2>&1))" >&2
      return 0
    fi
  done

  echo "ERROR: no se encontró un intérprete de Python funcional." >&2
  echo "       Se probaron: ${candidates[*]}" >&2
  echo "       En Windows, revisa Configuración > Aplicaciones > Alias de" >&2
  echo "       ejecución de aplicaciones y desactiva los alias de 'python'/'python3'" >&2
  echo "       si apuntan a la Microsoft Store, o instala Python 3.11+ desde" >&2
  echo "       https://www.python.org/downloads/ y agrégalo al PATH." >&2
  return 1
}
