#!/usr/bin/env bash
# Corre las 4 suites de evaluación de ai-testing-lab en secuencia
# (promptfoo, DeepEval, Ragas, security) y genera un resumen consolidado
# en Markdown bajo reports/<fecha>/<hora>/summary.md.
#
# Diseño: cada suite corre aunque una anterior haya fallado — este script
# nunca aborta a mitad de camino. El objetivo es un reporte honesto de qué
# pasó y qué no, no un gate estricto de CI. El código de salida final es
# el número de suites que fallaron (0 = todas OK), útil si en Fase 2 esto
# se conecta a un pipeline de CI/CD.
set -uo pipefail
cd "$(dirname "$0")/.."

# shellcheck source=lib/source_lab_env.sh
source "$(dirname "$0")/lib/source_lab_env.sh"
source_lab_env

RUN_DATE="$(date +%Y-%m-%d)"
RUN_TIME="$(date +%H%M%S)"
RUN_DIR="reports/${RUN_DATE}/${RUN_TIME}"
mkdir -p "$RUN_DIR/promptfoo" "$RUN_DIR/deepeval" "$RUN_DIR/ragas" "$RUN_DIR/security"

echo "==================================================================="
echo " ai-testing-lab · run_all_evals.sh"
echo " Resultados en: $RUN_DIR"
echo "==================================================================="

# Ejecuta un script capturando su salida a un log, sin dejar que un fallo
# aborte este script (no usamos `set -e` a propósito). Devuelve el exit
# code real del script (no el de `tee`) vía PIPESTATUS.
run_suite() {
  local script="$1" logfile="$2"
  "$script" 2>&1 | tee "$logfile"
  return "${PIPESTATUS[0]}"
}

# Best-effort: extrae la última línea que parezca un resumen de resultados
# de un log. Si no encuentra nada, no hace fallar el script.
last_match() {
  grep -E "$2" "$1" 2>/dev/null | tail -1 || true
}

echo ""
echo "==> [1/4] Prompt Testing (promptfoo)"
run_suite "./scripts/run_prompt_tests.sh" "$RUN_DIR/promptfoo/output.log"
PROMPTFOO_RC=$?
if [ "$PROMPTFOO_RC" -eq 0 ]; then PROMPTFOO_STATUS="✅ OK"; else PROMPTFOO_STATUS="❌ FALLÓ (exit $PROMPTFOO_RC)"; fi
PROMPTFOO_DETAIL="$(last_match "$RUN_DIR/promptfoo/output.log" '(passed|failed) \(')"

echo ""
echo "==> [2/4] DeepEval"
run_suite "./scripts/run_deepeval.sh" "$RUN_DIR/deepeval/output.log"
DEEPEVAL_RC=$?
if [ "$DEEPEVAL_RC" -eq 0 ]; then DEEPEVAL_STATUS="✅ OK"; else DEEPEVAL_STATUS="❌ FALLÓ (exit $DEEPEVAL_RC)"; fi
DEEPEVAL_DETAIL="$(last_match "$RUN_DIR/deepeval/output.log" '[0-9]+ (passed|failed|error)')"

echo ""
echo "==> [3/4] Ragas"
run_suite "./scripts/run_ragas.sh" "$RUN_DIR/ragas/output.log"
RAGAS_RC=$?
if [ "$RAGAS_RC" -eq 0 ]; then RAGAS_STATUS="✅ OK"; else RAGAS_STATUS="❌ FALLÓ (exit $RAGAS_RC)"; fi
if [ -f evals/ragas/last_run_results.csv ]; then
  cp evals/ragas/last_run_results.csv "$RUN_DIR/ragas/last_run_results.csv"
  RAGAS_DETAIL="métricas en \`ragas/last_run_results.csv\`"
else
  RAGAS_DETAIL="(no se generó CSV de resultados)"
fi

echo ""
echo "==> [4/4] Security (garak + promptfoo redteam)"
run_suite "./scripts/run_security_checks.sh" "$RUN_DIR/security/output.log"
SECURITY_RC=$?
if [ "$SECURITY_RC" -eq 0 ]; then SECURITY_STATUS="✅ OK"; else SECURITY_STATUS="❌ FALLÓ (exit $SECURITY_RC)"; fi
SECURITY_DETAIL="$(last_match "$RUN_DIR/security/output.log" '(garak|promptfoo):')"

FAILED_COUNT=0
for rc in "$PROMPTFOO_RC" "$DEEPEVAL_RC" "$RAGAS_RC" "$SECURITY_RC"; do
  [ "$rc" -ne 0 ] && FAILED_COUNT=$((FAILED_COUNT + 1))
done

SUMMARY_FILE="$RUN_DIR/summary.md"
{
  echo "# Resumen de evaluación — ai-testing-lab"
  echo ""
  echo "**Fecha:** ${RUN_DATE} ${RUN_TIME}"
  echo "**Suites fallidas:** ${FAILED_COUNT} / 4"
  echo ""
  echo "| Suite | Estado | Detalle | Log |"
  echo "|---|---|---|---|"
  echo "| Prompt Testing (promptfoo) | ${PROMPTFOO_STATUS} | ${PROMPTFOO_DETAIL:-—} | \`${RUN_DIR}/promptfoo/output.log\` |"
  echo "| DeepEval | ${DEEPEVAL_STATUS} | ${DEEPEVAL_DETAIL:-—} | \`${RUN_DIR}/deepeval/output.log\` |"
  echo "| Ragas | ${RAGAS_STATUS} | ${RAGAS_DETAIL:-—} | \`${RUN_DIR}/ragas/output.log\` |"
  echo "| Security (garak + promptfoo redteam) | ${SECURITY_STATUS} | ${SECURITY_DETAIL:-—} | \`${RUN_DIR}/security/output.log\` |"
  echo ""
  echo "## Notas"
  echo ""
  echo "- Este resumen no reemplaza revisar cada log individual."
  echo "- Un fallo en Security no necesariamente es un bug: promptfoo"
  echo "  redteam puede fallar/omitirse por el requisito de verificación de"
  echo "  email (ver \`docs/security-notes.md\`, sección \"Incidencias"
  echo "  conocidas\") — revisa el log para diferenciarlo de un fallo real."
  echo "- Antes de correr Ragas/DeepEval por primera vez, asegúrate de haber"
  echo "  indexado el RAG: \`curl -X POST http://localhost:8080/rag/ingest\`."
} > "$SUMMARY_FILE"

echo ""
echo "==================================================================="
echo " RESUMEN FINAL"
echo "==================================================================="
cat "$SUMMARY_FILE"
echo ""
echo "==> Resumen guardado en: $SUMMARY_FILE"

exit "$FAILED_COUNT"
