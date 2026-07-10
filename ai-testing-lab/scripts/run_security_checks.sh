#!/usr/bin/env bash
# Ejecuta las validaciones de seguridad disponibles: garak (recomendado,
# 100% local, sin registro) y/o red teaming con promptfoo (requiere
# verificación por email la primera vez, ver advertencia abajo). ModelScan
# se documenta aparte porque aplica solo cuando se descargan artefactos de
# modelo manualmente (ver evals/security/modelscan/README.md).
#
# Diseño: cada sección es independiente. Si una falla o se omite, las demás
# igual se ejecutan — el script nunca aborta por completo a mitad de camino.
# El resumen final dice exactamente qué corrió, qué falló y qué se omitió.
set -uo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] && set -a && source .env && set +a

GARAK_STATUS="omitido (no instalado)"
PROMPTFOO_STATUS="omitido (npx no disponible)"

echo "==================================================================="
echo " ADVERTENCIA: esto genera prompts adversariales (jailbreak, prompt"
echo " injection, etc.) contra tu modelo LOCAL. No apuntes esta config a"
echo " un endpoint de producción ni de terceros sin autorización."
echo "==================================================================="
echo ""
echo "Hay dos motores de red teaming disponibles, con un trade-off distinto:"
echo "  1) garak     -> 100% local, sin registro ni verificación de ningún tipo."
echo "  2) promptfoo -> más cómodo de configurar, pero 'redteam generate'"
echo "                  exige verificar un email la primera vez que se usa"
echo "                  (gratis, pero deja de ser un flujo 100% anónimo)."
echo ""
echo "Si no quieres dar ningún dato, deja que la sección de promptfoo falle"
echo "(o cancélala con Ctrl+C cuando pida el email) y confía solo en garak."
echo ""

# --- 1) garak: 100% local, sin ningún tipo de registro -----------------------
echo "==> [1/2] Smoke test con garak"
if command -v garak >/dev/null 2>&1; then
  export OPENAI_API_KEY="${OPENAI_API_KEY:-ollama-local-no-key-needed}"
  export OPENAI_BASE_URL="${OPENAI_BASE_URL:-http://localhost:11434/v1}"
  mkdir -p evals/security/garak/reports
  if garak \
      --model_type openai \
      --model_name "${OLLAMA_CHAT_MODEL:-llama3.2:1b}" \
      --probes promptinject,dan \
      --generations 2 \
      --report_prefix evals/security/garak/reports/smoke; then
    GARAK_STATUS="OK (ver evals/security/garak/reports/)"
  else
    GARAK_STATUS="FALLÓ (ver salida arriba)"
    echo "AVISO: garak terminó con error. Revisa la salida arriba." >&2
  fi
else
  echo "AVISO: garak no está instalado. Ver evals/security/garak/README.md"
  echo "       para instalarlo en un entorno virtual dedicado — es la opción"
  echo "       recomendada para red teaming 100% local, sin registro."
fi

echo ""

# --- 2) promptfoo redteam: requiere verificación de email, opcional --------
echo "==> [2/2] Red teaming con promptfoo (evals/security/promptfoo_redteam)"
if command -v npx >/dev/null 2>&1; then
  echo "    (la primera vez pedirá un email de verificación; Ctrl+C para omitir)"
  if (
    cd evals/security/promptfoo_redteam
    npx --yes promptfoo@latest redteam generate -c redteam_config.yaml &&
    npx --yes promptfoo@latest redteam eval -c redteam_config.yaml
  ); then
    PROMPTFOO_STATUS="OK"
  else
    PROMPTFOO_STATUS="FALLÓ u omitido (probablemente por la verificación de email)"
    echo "AVISO: el red teaming de promptfoo no completó. Es normal si" >&2
    echo "       cancelaste la verificación de email — usa garak si quieres" >&2
    echo "       evitarla por completo. Ver el comentario al inicio de" >&2
    echo "       evals/security/promptfoo_redteam/redteam_config.yaml." >&2
  fi
else
  echo "AVISO: npx no disponible, se omite el red teaming con promptfoo."
fi

echo ""
echo "==> Recordatorio: si vas a cargar un modelo descargado manualmente"
echo "    (no vía 'ollama pull'), escanéalo primero con ModelScan."
echo "    Ver evals/security/modelscan/README.md"

echo ""
echo "==================================================================="
echo " RESUMEN de seguridad"
echo "   garak:      $GARAK_STATUS"
echo "   promptfoo:  $PROMPTFOO_STATUS"
echo "==================================================================="

# El script termina en 0 siempre: es un reporte de estado, no un gate de
# CI. Si necesitas que falle el build cuando algo no corrió, revisa el
# resumen impreso arriba (esto se deja explícito a propósito, ver
# docs/testing-playbook.md).
exit 0
